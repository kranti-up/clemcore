import copy
from typing import List, Dict, Tuple
from string import ascii_lowercase as letters
import importlib

import numpy as np
import json

from fuzzywuzzy import process

import clemgame.metrics as ms
from clemgame.clemgame import GameMaster, GameBenchmark, GameScorer
from clemgame import get_logger

from games.dmsystem_monolithic_llm.players import LLMSpeaker
from games.dmsystem_monolithic_llm.computemetrics import ComputeMetrics
from games.dmsystem_monolithic_llm.instancegenerator import GAME_NAME
from games.dmsystem_monolithic_llm.gamevalidator import GameValidator
from games.dmsystem_monolithic_llm.dbquerybuilder import DBQueryBuilder

from games.dmsystem_monolithic_llm.utils import cleanupanswer


# use the framework logger to log events relevant at runtime;
# this is independent from the game records / transcript
logger = get_logger(__name__)


class DMSystemMaster(GameMaster):
    def __init__(
        self,
        gamename: str,
        experiment: Dict,
        player_backends: List[str],
        other_modules: classmethod,
    ):
        super().__init__(gamename, experiment, player_backends)

        # save experiment and player attributes that will be necessary later
        self.topic = experiment["name"]
        self.model_a = player_backends[0]
        self.model_b = player_backends[1]
        self.human_input = ["gradio", "slurk"]  # Add the human input backends here
        self.custom_dm = [
            "customtod-gpt-3.5",
            "customtod-opt-iml-1.3b",
        ]  # Add the custom DM backends here

        # initialise attributes that will be used for the evaluation scores
        self.aborted: bool = False
        self.lose: bool = False
        self.success: bool = False
        self.complete_turns: int = 0

        if other_modules:
            self.other_modules = other_modules

    def setup(self, data: Dict, game_id: int) -> None:
        """Setup the episode (mandatory)."""

        self._setcommonsetup(data, game_id)
        self._setgamespecificsetup(data, game_id)
        self._initothermodules(data)

        # add initial prompts to each player's messages
        self.initiate(self.prompt_player_a, self.prompt_player_b)

        # always log the details of the players in this format (see logdoc)
        self.log_players(
            {
                "GM": "Game master for DMSystem",
                "Player 1": f"Player A: {self.model_a}",
                "Player 2": f"Player B: {self.model_b}",
            }
        )

        # log any additional keys that will be relevant for evaluation
        self.log_key("n_turns", self.n_turns)

    def _setcommonsetup(self, data: Dict, game_id: int) -> None:
        self.game_id = game_id
        self.n_turns = data["n_turns"]
        self.similarity = data["similarity"]
        self.statusmsg = data["statusmsg"]

        self.domain = data["domain"]
        self.domaindbpath = data["domaindb_path"]
        self.domainschema = data["domain_schema"]
        self.goal = data["goal"]
        self.game_name = data["game_name"]
        self.slots = data["slots"]
        self.cat_slots = data["cat_slots"]
        self.noncat_slots = data["noncat_slots"]

        self.gamedata = None
        self.slots_gen = None
        self.misses = None

        self.prompt_player_a = data["prompt_a"]
        self.prompt_player_b = data["prompt_b"]

        self.turn_prompt_player_a = data["turn_prompt_a"]
        self.turn_prompt_player_b = data["turn_prompt_b"]
        self.dbquery_prompt_player_b = data["dbquery_prompt_b"]
        self.validbooking_prompt_player_b = data["validbooking_prompt_b"]

        # initialise game variables
        self.current_turn: int = 0

        self.num_booking_attempts = 0
        self.num_db_queries = 0

        # initialise common metrics
        self.request_counts = [0] * (self.n_turns + 1)
        self.parsed_request_counts = [0] * (self.n_turns + 1)
        self.violated_request_counts = [0] * (self.n_turns + 1)

    def _setgamespecificsetup(self, data: Dict, game_id: int) -> None:
        # instantiate both players
        mono_dm = importlib.import_module(
            "games.dmsystem_monolithic_llm.instancegenerator"
        )
        modular_dm = importlib.import_module(
            "games.dmsystem_modular_llm.instancegenerator"
        )
        modular_prog_dm = importlib.import_module(
            "games.dmsystem_modular_prog.instancegenerator"
        )

        custom_dm = importlib.import_module("games.dmsystem_customtod.instancegenerator")

        self.monolithic_llm_game_name = getattr(mono_dm, "GAME_NAME")
        self.modular_llm_game_name = getattr(modular_dm, "GAME_NAME")
        self.modular_prog_game_name = getattr(modular_prog_dm, "GAME_NAME")
        self.custom_dm_game_name = getattr(custom_dm, "GAME_NAME")

        if (
            data["game_name"] != self.custom_dm_game_name
            and self.model_b.model_spec["model_name"] in self.custom_dm
        ):
            raise ValueError(
                f"Model: {self.model_b.model_spec['model_name']} is not implemented for this game -> {data['game_name']}"
            )

        if data["game_name"] == self.monolithic_llm_game_name:
            self.player_a = LLMSpeaker(self.model_a, "A", self.goal, self.slots)
            self.player_b = LLMSpeaker(self.model_b, "B", "", self.slots)

        elif data["game_name"] in [self.modular_llm_game_name, self.modular_prog_game_name]:
            self.player_a = self.other_modules["speaker"](
                self.model_a, "A", self.goal, self.slots
            )
            self.player_b = self.other_modules["speaker"](
                self.model_b, "B", "", self.slots
            )

            self.turn_ss_prompt_player_b = data["turn_ss_prompt_b"]
            self.prompt_intent = data["intent_detection"]
            self.prompt_slot_extraction = data["slot_extraction"]
            self.prompt_followup_generation = data["followup_generation"]
            self.prompt_booking_aggregator = data["booking_aggregator"]

        elif data["game_name"] == self.custom_dm_game_name:
            self.player_a = LLMSpeaker(self.model_a, "A", self.goal, self.slots)
            self.player_b = self.other_modules["speaker"](
                self.model_b, "B", "", self.slots
            )

    def _initothermodules(self, data: Dict) -> None:
        self.gamevalidator = GameValidator(
            self.game_name, self.slots, self.cat_slots, self.noncat_slots, self.similarity["threshold"]
        )
        self.dbquery = DBQueryBuilder(
            self.domain,
            self.domaindbpath,
            self.domainschema,
            self.cat_slots,
            self.noncat_slots,
            self.similarity["threshold"],
            {"nocolumnmatch": self.statusmsg["nocolumnmatch"], "novaluematch": self.statusmsg["novaluematch"]},
        )

        if self.game_name in [self.modular_llm_game_name, self.modular_prog_game_name]:
            prompts_dict = {
                "turn_ss_prompt_b": self.turn_ss_prompt_player_b,
                "intent_detection": self.prompt_intent,
                "slot_extraction": self.prompt_slot_extraction,
                "followup_generation": self.prompt_followup_generation,
                "booking_aggregator": self.prompt_booking_aggregator,
            }

            self.modularb = self.other_modules["modules"](
                self.model_b, data, self.player_b, prompts_dict
            )
        elif self.game_name == self.custom_dm_game_name:
            self.modularb = self.other_modules["modules"](
                self.model_b.model_spec["model_name"], data["goal"]
            )

    def play(self) -> None:
        """Play the game until the end (mandatory)."""
        # play the game
        while self.proceed():
            self.current_turn += 1
            # always call log_next_turn when a new turn starts
            self.log_next_turn()
            self.turn()

        logger.info("Closing the DB connection")
        self.dbquery.reset()

        if self.complete_turns == self.n_turns:
            if not self.success:
                self.lose = True

        self.gamedata = {
            "task": self.goal,
            "slots_gt": self.slots,
            "slots_gen": self.slots_gen,
            "cat_slots": self.cat_slots,
            "noncat_slots": self.noncat_slots,
            "max_turns": self.n_turns,
            "play_turns": self.current_turn,
            "similarity": self.similarity,
        }

        # if self.complete_turns == self.n_turns:
        # log a message informing that the game was successfuly played
        gt_slots = "Ground truth slots:\n"+ json.dumps(self.slots)
        gen_slots = "Generated slots:\n"+ json.dumps(self.slots_gen)

        action = {
            "type": "info",
            "content": f"{gt_slots}\n{gen_slots}",
        }
        self.log_event(from_="GM", to="GM", action=action)

        if self.success:
            action = {
                "type": "info",
                "content": "The game is successful; all the slots matched.",
            }
        elif self.lose:
            if self.misses:
                action = {
                    "type": "info",
                    "content": "The game was lost due to a mismatch in the slots."
                    + "\n"
                    + json.dumps(self.misses),
                }
            elif self.complete_turns == self.n_turns:
                action = {
                    "type": "info",
                    "content": f"The game was lost as the maximum number of turns ({self.n_turns}) was reached",
                }
            else:
                action = {
                    "type": "info",
                    "content": f"lost game",
                }
        elif self.aborted:
            action = {
                "type": "info",
                "content": "The game has been aborted due to an invalid response.",
            }
        else:
            action = {
                "type": "info",
                "content": f"The game was lost after ({self.n_turns}) turns.",
            }
        self.log_event(from_="GM", to="GM", action=action)

        # log a final message saying that the game did came to an end
        action = {"type": "info", "content": "end game"}
        self.log_event(from_="GM", to="GM", action=action)
        # log all temporary game variables that are needed for evaluation
        self.log_eval_assets()

    def initiate(self, prompt_player_a: str, prompt_player_b: str) -> None:
        """Initialise the dialogue history (firstlast specific)."""
        # always call log_next_turn what a turn starts
        self.log_next_turn()

        # append the initial message of each player to their history
        # the value user means the message is from an interlocutor of the model
        if self.model_a.model_spec["model_name"] in self.human_input:
            user_welcome = self.statusmsg["welcome"].replace("$domain", self.domain)
            self.player_a.history.append({"role": "user", "content": user_welcome})
        else:
            self.player_a.history.append({"role": "user", "content": prompt_player_a})

        if self.game_name != self.custom_dm_game_name:
            self.player_b.history.append({"role": "user", "content": prompt_player_b})

        # also log the messages as events for the transcriptions
        action = {"type": "send message", "content": prompt_player_a}
        self.log_event(from_="GM", to="Player 1", action=action)
        # action = {'type': 'send message', 'content': prompt_player_b}
        # self.log_event(from_='GM', to='Player 2', action=action)

    def proceed(self) -> None:
        """Check if the game loop should continue (dmsystem specific)."""
        return (
            self.current_turn < self.n_turns
            and not self.aborted
            and not self.lose
            and not self.success
        )

    def turn(self) -> None:
        """Perform a game turn, utterances by A and B (firstlast specific)."""
        # get player A's reply and add it to its history
        status, response, details = self._triggerplayer("a")

        if status is None:
            # stop game
            return None

        if self.success or self.lose or self.aborted:
            return None

        # add A's reply to B's history
        logger.info(f"Appended Player A answer to PlayerB\n{response}")
        self._append_utterance(response, "b", "user")
        # also add the reply to the transcript
        action = {
            "type": "send message",
            "content": self.player_b.history[-1]["content"],
        }
        self.log_event(from_="GM", to="Player 2", action=action)

        # now do the same for player B
        status, response, details = self._triggerplayer("b")
        if status is None:
            # stop game
            return None
        
        while True:
            if response == "follow-up":
                self._handleplayerb_response(details)
                break

            elif response == "db-query":
                # handle db query
                status, response, details = self._handle_dbquery(details)
                if status is None:
                    # stop game
                    self.aborted = True
                    # log the abortion event
                    action = {"type": "invalid format", "content": "abort"}
                    self.log_event(from_="GM", to="GM", action=action)
                    # increase the counter of requests that violate form rules
                    self.violated_request_counts[self.current_turn] += 1
                    return None
                
            elif response == "validate-booking":
                # handle booking
                status, response, details = self._handle_booking(details)
                if status is None:
                    # stop game
                    self.aborted = True
                    # log the abortion event
                    action = {"type": "invalid format", "content": "abort"}
                    self.log_event(from_="GM", to="GM", action=action)
                    # increase the counter of requests that violate form rules
                    self.violated_request_counts[self.current_turn] += 1
                    return None
            
        self.complete_turns += 1



    def _get_utterance(self, player: str) -> str:
        """Get utterance from a player and log it (firstlast specific)."""
        assert player in ("a", "b")
        if player == "a":
            if (
                self.current_turn == 1
                and self.model_a.model_spec["model_name"] in self.human_input
            ):
                usergoal = self.statusmsg["usergoal"].replace("$goal", self.goal)
                usergoal += "\n" + "Additional information:\nbookday: Friday, people: 4, time: 14:15,\nfood: chinese, price: cheap, name: charlie chan\n"
                self.player_a.history[-1]["content"] += "\n\n" + usergoal
            # make an API call (or get a programmatic response) from player a
            prompt, raw_answer, answer = self.player_a(
                self.player_a.history, self.current_turn
            )
            # add API call to the records
            action = {"type": "get message", "content": answer}
            self.log_event(
                from_="Player 1",
                to="GM",
                action=action,
                call=(copy.deepcopy(prompt), raw_answer),
            )
            # add reply to its own memory
            self._append_utterance(answer, "a", "assistant")

        else:
            # make an API call (or get a programmatic response) from player b
            if self.game_name == self.monolithic_llm_game_name:
                if len(self.player_b.history) >= 2:
                    if self.player_b.history[-2]["role"] == self.player_b.history[-1]["role"]:
                        print("Player B: Repeating the same role")
                        print(self.player_b.history)
                        input()


                prompt, raw_answer, answer = self.player_b(
                    self.player_b.history, self.current_turn
                )
                answer = cleanupanswer(answer)

                # add reply to its own memory
                self._append_utterance(answer, "b", "assistant")

            elif self.game_name in [self.modular_llm_game_name, self.modular_prog_game_name]:
                prevlen = len(self.player_b.history)
                prompt, raw_answer, answer = self.modularb.run(self.current_turn)
                # Don't add answer to player b's history, as it is already added in the modularb.run method
                curlen = len(self.player_b.history)

                for i in range(prevlen, curlen-1):
                    action = {
                        "type": "info",
                        "content": self.player_b.history[i]["content"],
                    }
                    self.log_event(from_="Player 2", to="Player 2", action=action)


            elif self.game_name == self.custom_dm_game_name:
                prompt, raw_answer, answer = self.modularb.run(self.player_b.history[-1]["content"], self.current_turn)

            # add API call to the records
            action = {"type": "get message", "content": answer}
            self.log_event(
                from_="Player 2",
                to="GM",
                action=action,
                call=(copy.deepcopy(prompt), raw_answer),
            )

        # increase the number of API requests
        self.request_counts[self.current_turn] += 1
        return answer

    def _append_utterance(self, utterance: str, player: str, role: str) -> None:
        """Add an utterance to the history of a player (firstlast specific)."""
        assert player in ("a", "b")
        logger.info(
            f"Player {player}: {type(utterance)}, {utterance} current turn = {self.current_turn}"
        )
        if player == "a":
            if role == "assistant":
                self.player_a.history.append({"role": role, "content": utterance})
            else:
                if isinstance(utterance, dict):
                    b_response = json.dumps(utterance)
                else:
                    b_response = utterance

                if self.model_a.model_spec["model_name"] in self.human_input:
                    content = self.statusmsg["dmresponse"].replace(
                        "$response", "\n" + b_response
                    )

                else:
                    content = self.turn_prompt_player_a + "\n\n" + b_response

                self.player_a.history.append({"role": role, "content": content})
        else:
            if role == "assistant":
                if isinstance(utterance, dict):
                    b_response = json.dumps(utterance)
                else:
                    b_response = utterance
                self.player_b.history.append({"role": role, "content": b_response})

            else:
                if len(self.player_b.history) == 1:
                    #TODO: check for cases, where player_b.history is empty
                    self.player_b.history[-1]["content"] += "\n\n" + utterance
                else:
                    if isinstance(utterance, dict):
                        b_response = json.dumps(utterance)
                    else:
                        b_response = utterance

                    if role == "user":
                        turn_prompt = self.turn_prompt_player_b
                    elif role == "db-query":
                        turn_prompt = self.dbquery_prompt_player_b
                    elif role == "validate-booking":
                        turn_prompt = self.validbooking_prompt_player_b

                    self.player_b.history.append({"role": "user", "content": turn_prompt + "\n\n" + b_response})
                    logger.info(f"Player B: {self.player_b.history[-1]}")


    def _isvalidturn(self, player: str, answer: str) -> bool:
        """Check if answer is valid and correct (firstlast specific)."""
        # parse answer
        response, details = self.parse(player, answer)
        # print(f"Check Validity: isdone:{isdone}, details: {details}")
        logger.info(
            f"_isvalidturn(): player: {player}, response: {response} details: {details}"
        )

        if response is None:
            self.aborted = True
            # log the abortion event
            action = {"type": "invalid format", "content": "abort"}
            self.log_event(from_="GM", to="GM", action=action)
            # increase the counter of requests that violate form rules
            self.violated_request_counts[self.current_turn] += 1
            return False, response, details

        # increase the counter of requests that conform to form rules
        self.parsed_request_counts[self.current_turn] += 1
        # log the event that the string was valid (no strange characters)
        action = {"type": "metadata", "content": "response confirms to rules"}
        self.log_event(from_="GM", to="GM", action=action)

        return True, response, details

    def _process_player_response(self, player: str, response: str, details: str) -> None:
        if player == "a":
            if "done" in response:
                if response.lower() == "done":
                    action = {"type": "parse", "content": f"received done"}
                    self.log_event(from_="GM", to="GM", action=action)

                    # Compare the slots of the ground truth and the generated slots
                    status, missed_values = self.gamevalidator.run(self.slots_gen)
                    if status:
                        self.success = True
                    else:
                        self.lose = True
                        self.misses = missed_values
                else:
                    self.aborted = True
                    # log the abortion event
                    action = {"type": "invalid format", "content": "abort"}
                    self.log_event(from_="GM", to="GM", action=action)
                    # increase the counter of requests that violate form rules
                    self.violated_request_counts[self.current_turn] += 1                 
        else:
            pass

    
    def _triggerplayer(self, player: str) -> Tuple[bool, str, str]:
        answer = self._get_utterance(player)
        # print(f"3. Player B answer\n{answer_b}")
        logger.info(f"Player-{player} answer\n{answer}")
        is_valid_turn, response, details = self._isvalidturn(player, answer)

        logger.info(
            f"Player-{player} is_valid_turn: {is_valid_turn}, response: {response}, details: {details}"
        )
        if not is_valid_turn:
            # stop game
            return None, response, details
        
        self._process_player_response(player, response, details)
        return True, response, details
    
    def _handleplayerb_response(self, details) -> None:
        # add B's reply to A's history
        if self.current_turn < self.n_turns:
            logger.info(f"Appended Player B answer to PlayerA\n{details}")
            self._append_utterance(details, "a", "user")
            # also add the reply to the transcript
            action = {
                "type": "send message",
                "content": self.player_a.history[-1]["content"],
            }
            self.log_event(from_="GM", to="Player 1", action=action)
    
    def _isdbquery(self, status) -> bool:
        if isinstance(status, str) and status == "db-query":
            return True
        return False
    
   
    def _handle_booking(self, details) -> bool:
        if not isinstance(details, dict):
            return False, None, details
        

        reformat_keys = {"bookday": "day", "bookpeople": "people", "booktime": "time",
                          "bookstay": "stay", "price": "pricerange", "location": "area",
                          "food": "cuisine"}

        #compare the slots and values if they are in available
        slot_values = {}
        for slot in self.slots:
            slot_values[slot] = self.dbquery.get_valid_values(slot)

        while True:
            if self.num_booking_attempts >= self.n_turns or details is None:
                # stop game
                logger.info(f"Booking attempts exceeded {self.num_booking_attempts} or error in details: {details}")
                self.num_booking_attempts = 0
                return None, None, None

            logger.info(f"continuing with booking confirmation for: {details}")

            missing_slots = []
            use_match = {}
            message = ""
            for slot in self.slots:
                if slot not in details:
                    match, score = process.extractOne(slot, details.keys())
                    if score < self.similarity["threshold"]:
                        missing_slots.append(slot)
                    else:
                        use_match.update({match: slot})

            if missing_slots:
                missing_slots_info = self.statusmsg["missing_slots"].replace("$slots", ", ".join(missing_slots))
                message = "Missed some slots: " + missing_slots_info

            else:
                # check if the values are valid
                for slot, slotvalue in details.items():
                    if slot in slot_values:
                        if not slot_values[slot]:
                            continue
                        if slotvalue not in slot_values[slot]:
                            invalid_value_info = self.statusmsg["invalid_value"].replace("$slot", slot) + f" -> possible values: {slot_values[slot]}\n"
                            message += invalid_value_info
                    else:
                        if slot in use_match:
                            if use_match[slot] in slot_values:
                                if not slot_values[use_match[slot]]:
                                    continue
                                if slotvalue not in slot_values[use_match[slot]]:
                                    invalid_value_info = self.statusmsg["invalid_value"].replace("$slot", use_match[slot]) + f" -> possible values: {slot_values[use_match[slot]]}\n"
                                    message += invalid_value_info 
            if not message:
                message = f"{self.statusmsg['success']} {self.statusmsg['validatebooking']}\n{self.statusmsg['booking_reference']}"
                self.slots_gen = details
                # log the fact that the booking is completed
                action = {"type": "parse", "content": f"booking completed"}
                self.log_event(from_="GM", to="GM", action=action)

            '''
            missing_slots = []
            use_match = {}
            for slot in self.slots:
                if slot not in details:
                    match, score = process.extractOne(slot, details.keys())
                    if score < self.similarity["threshold"]:
                        missing_slots.append(slot)
                    else:
                        use_match.update({match: slot})

            if missing_slots:
                message = f"{self.statusmsg['failure']} {self.statusmsg['validatebooking']}\n"
                missing_slots_info = self.statusmsg["missing_slots"].replace("$slots", ", ".join(miss_slots))
                message += missing_slots_info

            else:
                # check if the values are valid
                for slot, slotvalue in details.items():
                    if slot in slot_values:
                        if slotvalue not in slot_values[slot]:
                            invalid_value_info = self.statusmsg["invalid_value"].replace("$slot", slot)
                            message += invalid_value_info
                    else:
                        if slot in use_match:
                            if use_match[slot] in slot_values:
                                if slotvalue not in slot_values[use_match[slot]]:
                                    invalid_value_info = self.statusmsg["invalid_value"].replace("$slot", use_match[slot])
                                    message += invalid_value_info                 


            message = ""
            missing_slots = [slot for slot in self.slots if slot not in details]
            miss_slots = []
            if missing_slots:
                for slot in self.slots:
                    if slot in reformat_keys:
                        if reformat_keys[slot] not in details:
                            miss_slots.append(reformat_keys[slot])
                    else:
                        if slot not in details:
                            miss_slots.append(slot)
                if miss_slots:
                    message = f"{self.statusmsg['failure']} {self.statusmsg['validatebooking']}\n"
                    missing_slots_info = self.statusmsg["missing_slots"].replace("$slots", ", ".join(miss_slots))
                    message += missing_slots_info

            if not miss_slots:
                # check if the values are valid
                message = f"{self.statusmsg['failure']} {self.statusmsg['validatebooking']}\n"
                for slot, slotvalue in details.items():
                    if slot not in slot_values:
                        usekey = ""
                        for key, value in reformat_keys.items():
                            if value == slot:
                                usekey = key
                                if not usekey in slot_values or not slot_values[usekey]:
                                    break
                                if slotvalue not in slot_values[usekey]:
                                    invalid_value_info = self.statusmsg["invalid_value"].replace("$slot", usekey)
                                    message += invalid_value_info
                                break
                    elif not slot_values[slot]:
                        continue
                    else:
                        if slotvalue not in slot_values[slot]:
                            invalid_value_info = self.statusmsg["invalid_value"].replace("$slot", slot)
                            message += invalid_value_info
                else:
                    message = f"{self.statusmsg['success']} {self.statusmsg['validatebooking']}\n{self.statusmsg['booking_reference']}"
                    self.slots_gen = details
                    # log the fact that the booking is completed
                    action = {"type": "parse", "content": f"booking completed"}
                    self.log_event(from_="GM", to="GM", action=action)
            '''

            if not message:
                print("Message is empty")
                input()
                raise ValueError("Message is empty")

            logger.info(f"Booking Message: {message}")
            self._append_utterance(message, "b", "validate-booking")
            # also add the reply to the transcript
            action = {
                "type": "send message",
                "content": self.player_b.history[-1]["content"],
            }
            self.log_event(from_="GM", to="Player 2", action=action)
            status, response, details = self._triggerplayer("b")
            logger.info(f"status is {status}, response: {response} details: {details}")
            if status is None:
                # stop game
                self.num_booking_attempts = 0
                return None, response, details

            if response in ["follow-up", "db-query"]:
                self.num_booking_attempts = 0
                return status, response, details
            else:
                self.num_booking_attempts += 1
                continue
        

    def _handle_dbquery(self, details) -> bool:
        dbcolumns = self.dbquery.getcolumns()
        while True:
            if self.num_db_queries >= self.n_turns or details is None:
                # stop game
                logger.info(f"DBQuery attempts exceeded {self.num_booking_attempts} or error in details: {details}")
                self.num_booking_attempts = 0
                return None, None, None

            slots = details
            logger.info(f"continuing with db query slots = {slots}")
            dbresult = self.dbquery.run(slots)
            message = f'{self.statusmsg[dbresult["status"]]} {self.statusmsg["dbfetch"]}\n'
            if dbresult["status"] == "success":
                message += json.dumps(dbresult["data"])
            else:
                availcolumns = self.statusmsg["availablecolumns"].replace(
                    "$columns", ", ".join(dbcolumns)
                )
                message += f'{dbresult["error"]}\n\n{availcolumns}'
            
            self._append_utterance(message, "b", "db-query")
            # also add the reply to the transcript
            action = {
                "type": "send message",
                "content": self.player_b.history[-1]["content"],
            }
            self.log_event(from_="GM", to="Player 2", action=action)            
            status, response, details = self._triggerplayer("b")
            logger.info(f"status is {status}, response: {response} details: {details}")
            if status is None:
                # stop game
                self.num_db_queries = 0
                return None, response, details
            

            #Recheck if follow-up and db-query to be handled separately: same in _handle_booking() API
            
            if response in ["follow-up", "validate-booking"]:
                self.num_db_queries = 0
                return status, response, details
            else:
                self.num_db_queries += 1
                continue


    @staticmethod
    def parse(player: str, utterance: str) -> bool:
        """Check if utterance is valid and return first/last tokens (firstlast specific)."""
        if player == "a":
            utterance = utterance.lower().strip()
            return utterance, None
        else:
            try:
                if isinstance(utterance, str):
                    result = json.loads(utterance)

                elif isinstance(utterance, dict):
                    result = utterance

                else:
                    return None, None

                return result["status"], result["details"]
            except Exception as e:
                logger.error(f"Error parsing utterance: {utterance}, {type(utterance)}")
                return None, None

    def log_eval_assets(self) -> None:
        """Aux to log variables needed for scoring (firstlast specific)"""
        self.log_key("Played turns", self.current_turn)
        self.log_key("Complete turns", self.complete_turns)
        self.log_key(ms.METRIC_ABORTED, self.aborted)
        self.log_key(ms.METRIC_LOSE, self.lose)
        self.log_key(ms.METRIC_REQUEST_COUNT, self.request_counts)
        self.log_key(ms.METRIC_REQUEST_COUNT_PARSED, self.parsed_request_counts)
        self.log_key(ms.METRIC_REQUEST_COUNT_VIOLATED, self.violated_request_counts)
        self.log_key("Evaluation", self.gamedata)


class DMSystemScorer(GameScorer):
    def __init__(self, game_name: str, experiment: Dict, game_instance: Dict):
        super().__init__(game_name, experiment, game_instance)
        self.cm = ComputeMetrics()

    def compute_scores(self, episode_interactions: Dict) -> None:
        played_turns = episode_interactions["Played turns"]
        complete_turns = episode_interactions["Complete turns"]
        # turn 0 was only the initial prompts, so we disregard it here
        reqs = episode_interactions[ms.METRIC_REQUEST_COUNT][1:]
        p_reqs = episode_interactions[ms.METRIC_REQUEST_COUNT_PARSED][1:]
        v_reqs = episode_interactions[ms.METRIC_REQUEST_COUNT_VIOLATED][1:]
        n_turns = len(reqs)

        for turn in range(0, played_turns):
            self.log_turn_score(turn, ms.METRIC_REQUEST_COUNT, reqs[turn])
            self.log_turn_score(turn, ms.METRIC_REQUEST_COUNT_PARSED, p_reqs[turn])
            self.log_turn_score(turn, ms.METRIC_REQUEST_COUNT_VIOLATED, v_reqs[turn])

        aborted = int(episode_interactions[ms.METRIC_ABORTED])
        lose = int(episode_interactions[ms.METRIC_LOSE]) if not aborted else 0
        success = 1 - lose if not aborted else 0
        bench_score = complete_turns / n_turns if not aborted else np.nan

        self.log_episode_score(ms.METRIC_ABORTED, aborted)
        self.log_episode_score(ms.METRIC_LOSE, lose)
        self.log_episode_score(ms.METRIC_SUCCESS, success)
        self.log_episode_score(ms.METRIC_REQUEST_COUNT, sum(reqs))
        self.log_episode_score(ms.METRIC_REQUEST_COUNT_PARSED, sum(p_reqs))
        self.log_episode_score(ms.METRIC_REQUEST_COUNT_VIOLATED, sum(v_reqs))
        self.log_episode_score(ms.METRIC_REQUEST_SUCCESS, sum(p_reqs) / sum(reqs))
        self.log_episode_score(ms.BENCH_SCORE, bench_score)

        self.log_episode_score("Played turns", played_turns)
        self.log_episode_score("Complete turns", complete_turns)
        self.log_episode_score("Max turns", n_turns)


        #results = episode_interactions["Evaluation"]
        # logger.error(f"Eval Results: {results}")
        # with open("/home/admin/Desktop/codebase/cocobots/clembenchfork_dm_code/clembench/reval/results.json", "w") as f:
        #    json.dump(results, f)
        '''
        accuracy, partialacc, missdata = self.cm.run(results)

        self.log_episode_score("accuracy", accuracy)
        self.log_episode_score("partial_accuracy", partialacc)
        self.log_episode_score("missdata", missdata)
        '''



class DMSystemBenchmark(GameBenchmark):
    """Integrate the game into the benchmark run."""

    def __init__(self):
        super().__init__(GAME_NAME)

    # defines whether the game is single player or not
    def is_single_player(self):
        return False

    # add a description of your game
    def get_description(self):
        return (
            "A simple game in which a human collaborate with a bot to complete a task."
        )

    # copy this, replacing the name of the game master in the return statement
    def create_game_master(
        self, experiment: Dict, player_backends: List[str]
    ) -> GameMaster:
        return DMSystemMaster(self.name, experiment, player_backends, None)

    def create_game_scorer(self, experiment: Dict, game_instance: Dict) -> GameScorer:
        return DMSystemScorer(self.name, experiment, game_instance)
