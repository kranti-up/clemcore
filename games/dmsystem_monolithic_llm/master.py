import random
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

from games.dmsystem_monolithic_llm.utils import cleanupanswer, generate_reference_number


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
        if self.game_name != self.custom_dm_game_name:
            self.initiate(self.prompt_player_a, self.prompt_player_b)
        else:
            self.initiate(self.prompt_player_a, None)

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
        self.respformat = data["json_schema"]
        self.domaindbkeys = data["domaindbkeys"]  

        self.gamedata = None
        self.slots_gen = None
        self.misses = None

        # initialise game variables
        self.current_turn: int = 0

        self.num_booking_attempts = 0
        self.num_db_queries = 0

        # initialise common metrics
        self.request_counts = [0] * (self.n_turns + 1)
        self.parsed_request_counts = [0] * (self.n_turns + 1)
        self.violated_request_counts = [0] * (self.n_turns + 1)

    def _save_prompts(self, data):
        self.prompt_player_a = data["prompt_a"]
        self.turn_prompt_player_a = data["turn_prompt_a"]

        if data["game_name"] != self.custom_dm_game_name:
            self.prompt_player_b = data["prompt_b"]
            self.turn_prompt_player_b = data["turn_prompt_b"]
            self.dbquery_prompt_player_b = data["dbquery_prompt_b"]
            self.validbooking_prompt_player_b = data["validbooking_prompt_b"]

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

        modular_hybrid_dm = importlib.import_module(
            "games.dmsystem_modular_hybrid.instancegenerator"
        )        

        custom_dm = importlib.import_module("games.dmsystem_customtod.instancegenerator")

        self.monolithic_llm_game_name = getattr(mono_dm, "GAME_NAME")
        self.modular_llm_game_name = getattr(modular_dm, "GAME_NAME")
        self.modular_prog_game_name = getattr(modular_prog_dm, "GAME_NAME")
        self.modular_hybrid_game_name = getattr(modular_hybrid_dm, "GAME_NAME")
        self.custom_dm_game_name = getattr(custom_dm, "GAME_NAME")

        self._save_prompts(data)

        if data["game_name"] == self.monolithic_llm_game_name:
            self.player_a = LLMSpeaker(self.model_a, "A", self.goal, self.slots)
            self.player_b = LLMSpeaker(self.model_b, "B", "", self.slots)

        elif data["game_name"] in [self.modular_llm_game_name, self.modular_prog_game_name,
                                   self.modular_hybrid_game_name]:
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
            self.prompt_dbquery_formatter = data["dbquery_formatter"]
            self.prompt_booking_formatter = data["booking_formatter"]
            #self.prompt_booking_aggregator = data["booking_aggregator"]

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

        if self.game_name in [self.modular_llm_game_name, self.modular_prog_game_name,
                              self.modular_hybrid_game_name]:
            prompts_dict = {
                "turn_ss_prompt_b": self.turn_ss_prompt_player_b,
                "intent_detection": self.prompt_intent,
                "slot_extraction": self.prompt_slot_extraction,
                "followup_generation": self.prompt_followup_generation,
                "dbquery_formatter": self.prompt_dbquery_formatter,
                "booking_formatter": self.prompt_booking_formatter,
                #"booking_aggregator": self.prompt_booking_aggregator,
            }

            reqdata = { "json_schema": self.respformat,
                       "liberal_processing": data["liberal_processing"],
                       "prompts_dict": prompts_dict,}

            self.modularb = self.other_modules["modules"](
                self.model_b, reqdata, self.player_b)
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

        logger.info(f"Player B history\n{self.player_b.history}")

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

        if self.game_name in [self.modular_llm_game_name, self.monolithic_llm_game_name]:
            self.player_b.history.append({"role": "user", "content": prompt_player_b})
        elif self.game_name in [self.modular_prog_game_name, self.modular_hybrid_game_name]:
            self.player_b.history.append({"role": "user", "content": "USER REQUEST:"})
        elif self.game_name == self.custom_dm_game_name:
            self.player_b.history.append({"role": "user", "content": ""})

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
                    action = {"type": "invalid format", "content": "game aborted due to an issue in dbquery"}
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
                    action = {"type": "invalid format", "content": "game aborted due to an issue in booking"}
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
                self.player_a.history, self.current_turn, None
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
                prompt, raw_answer, answer = self.player_b(
                    self.player_b.history, self.current_turn, self.respformat
                )
                logger.info(f"Player B: Before cleanup: {answer} {type(answer)}")
                answer = cleanupanswer(answer)
                logger.info(f"Player B: After cleanup: {answer} {type(answer)}") 

                # add reply to its own memory
                self._append_utterance(answer, "b", "assistant")
                logger.info(f"Player B: After appending: {answer} {type(answer)}") 

            elif self.game_name in [self.modular_llm_game_name, self.modular_prog_game_name,
                                    self.modular_hybrid_game_name]:
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
                # add reply to its own memory
                self._append_utterance(answer, "b", "assistant")                

            # add API call to the records
            action = {"type": "get message", "content": answer}
            self.log_event(
                from_="Player 2",
                to="GM",
                action=action,
                call=(copy.deepcopy(prompt), raw_answer),
            )

        # increase the number of API requests
        #TODO: For Modular DM, there are multiple calls to the sub-modules which are not counted here
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
                    self.player_b.history[-1]["content"] = self.player_b.history[-1]["content"].strip()
                else:
                    if isinstance(utterance, dict):
                        b_response = json.dumps(utterance)
                    else:
                        b_response = utterance

                    if role == "user":
                        if self.game_name in [self.modular_llm_game_name, self.monolithic_llm_game_name]:
                            turn_prompt = self.turn_prompt_player_b
                        if self.game_name in [self.modular_prog_game_name, self.modular_hybrid_game_name]:
                            turn_prompt = "USER REQUEST:"
                        elif self.game_name == self.custom_dm_game_name:
                            turn_prompt = ""                 
                    elif role == "db-query":
                        turn_prompt = self.dbquery_prompt_player_b
                        if self.game_name in [self.modular_prog_game_name, self.modular_hybrid_game_name]:
                            turn_prompt = "DATABASE RETRIEVAL RESULTS:"

                    elif role == "validate-booking":
                        turn_prompt = self.validbooking_prompt_player_b
                        if self.game_name in [self.modular_prog_game_name, self.modular_hybrid_game_name]:
                            turn_prompt = "BOOKING VALIDATION STATUS:"

                    b_message = turn_prompt + "\n\n" + b_response
                    self.player_b.history.append({"role": "user", "content": b_message.strip()})
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
            action = {"type": "invalid format", "content": "game aborted due to an issue in parsing the response"}
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
                    # This comparison is done in handle_booking() method
                    if self.game_name == self.custom_dm_game_name:
                        self.slots_gen = self.modularb.getgenslots()
                        logger.info(f"Generated slots in Player2: {self.slots_gen}")

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
        logger.info(f"Player-{player} answer\n{answer} {type(answer)}")
        is_valid_turn, response, details = self._isvalidturn(player, answer)

        logger.info(
            f"Player-{player} is_valid_turn: {is_valid_turn}, response: {response}, details: {details} {type(details)}"
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

        while True:
            if self.num_booking_attempts >= self.n_turns or details is None:
                # stop game
                logger.info(f"Booking attempts exceeded {self.num_booking_attempts} or error in details: {details}")
                self.num_booking_attempts = 0
                return None, None, None

            logger.info(f"continuing with booking confirmation for: {details}, gt_slots: {self.slots}")

            missing_slots = [slot for slot in self.slots if slot not in details]
            message = ""

            if missing_slots:
                missing_slots_info = self.statusmsg["missing_slots"].replace("$slots", ", ".join(missing_slots))
                message = "Missed some slots: " + missing_slots_info

            else:
                # Check if the values are valid
                missing_values = []
                only_book_slots = list(set(self.slots.keys()) - set(self.domaindbkeys))
                db_book_slots = list(set(self.slots.keys()) - set(only_book_slots))
                booking_query_details = self.respformat["schema"]["properties"]["details"]["oneOf"][2]["properties"]
                for slot in only_book_slots:
                    if slot in booking_query_details and "enum" in booking_query_details[slot]:
                        if details[slot] not in booking_query_details[slot]["enum"]:
                            missing_values.append(slot)

                if missing_values:
                    invalid_value_info = self.statusmsg["invalid_value"].replace("$slot", ", ".join(missing_values))
                    message += invalid_value_info
                
                else:
                    db_query_data = {}
                    db_query_details = self.respformat["schema"]["properties"]["details"]["oneOf"][1]["properties"]
                    for slot in db_book_slots:
                        if slot in db_query_details:
                            if "enum" in db_query_details[slot]:
                                if details[slot] not in db_query_details[slot]["enum"]:
                                    missing_values.append(slot)
                                else:
                                    db_query_data.update({slot: details[slot]})
                            else:
                                db_query_data.update({slot: details[slot]})
                    if missing_values:
                        invalid_value_info = self.statusmsg["invalid_value"].replace("$slot", ", ".join(missing_values))
                        message += invalid_value_info

                    else:
                        #Make a DB Query and check if the value is present in the DB
                        dbquery_result = self.dbquery.run(db_query_data)
                        if dbquery_result["status"] == "success":
                            #Fetch the booking reference number
                            bookrefnum = generate_reference_number()
                            refnumber = self.statusmsg['booking_reference'].replace("$refnum", bookrefnum)
                            message = f"{self.statusmsg['success']} {self.statusmsg['validatebooking']}\n{refnumber}"
                            self.slots_gen = details
                            # log the fact that the booking is completed
                            action = {"type": "parse", "content": f"booking completed"}
                            self.log_event(from_="GM", to="GM", action=action)
                        else:
                            missing_values = list(db_query_data.keys())
                            invalid_value_info = self.statusmsg["invalid_value"].replace("$slot", ", ".join(missing_values))
                            message += invalid_value_info

            if not message:
                logger.error("Message is empty")
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



    def _handle_booking_old(self, details) -> bool:
        if not isinstance(details, dict):
            return False, None, details


        while True:
            if self.num_booking_attempts >= self.n_turns or details is None:
                # stop game
                logger.info(f"Booking attempts exceeded {self.num_booking_attempts} or error in details: {details}")
                self.num_booking_attempts = 0
                return None, None, None

            logger.info(f"continuing with booking confirmation for: {details}")

            missing_slots = [slot for slot in self.slots if slot not in details]
            message = ""

            if missing_slots:
                missing_slots_info = self.statusmsg["missing_slots"].replace("$slots", ", ".join(missing_slots))
                message = "Missed some slots: " + missing_slots_info

            else:
                # check if the values are valid
                missing_values = []
                for slot, slotvalue in self.slots.items():
                    if isinstance(slotvalue, list):
                        if details[slot] not in slotvalue:
                            missing_values.append(slot)
                    else:
                        if details[slot] != slotvalue:
                            missing_values.append(slot)

                if missing_values:
                    invalid_value_info = self.statusmsg["invalid_value"].replace("$slot", ", ".join(missing_values))
                    message += invalid_value_info

                else:
                    #Fetch the booking reference number
                    bookrefnum = generate_reference_number()
                    refnumber = self.statusmsg['booking_reference'].replace("$refnum", bookrefnum)
                    message = f"{self.statusmsg['success']} {self.statusmsg['validatebooking']}\n{refnumber}"
                    self.slots_gen = details
                    # log the fact that the booking is completed
                    action = {"type": "parse", "content": f"booking completed"}
                    self.log_event(from_="GM", to="GM", action=action)


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
        while True:
            if self.num_db_queries >= self.n_turns or details is None:
                # stop game
                logger.info(f"DBQuery attempts exceeded {self.num_booking_attempts} or error in details: {details}")
                self.num_booking_attempts = 0
                return None, None, None

            slots = details
            logger.info(f"continuing with db query slots = {slots} {type(slots)}")
            dbresult = self.dbquery.run(slots)
            message = f'{self.statusmsg[dbresult["status"]]} {self.statusmsg["dbfetch"]}\n'
            if dbresult["status"] == "success":
                message += json.dumps(dbresult["data"])
            else:
                availcolumns = self.statusmsg["availablecolumns"].replace(
                    "$columns", ", ".join(self.domaindbkeys)
                )
                if not self.domaindbkeys:
                    logger.error("Domain DB keys are empty")
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
