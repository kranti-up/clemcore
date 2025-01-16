import copy
from typing import List, Dict, Tuple
from string import ascii_lowercase as letters
import importlib

import numpy as np
import json

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

        # initialise game variables
        self.current_turn: int = 0

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
        custom_dm = importlib.import_module("games.dmsystem_customtod.instancegenerator")

        self.monolithic_llm_game_name = getattr(mono_dm, "GAME_NAME")
        self.modular_llm_game_name = getattr(modular_dm, "GAME_NAME")
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

        elif data["game_name"] == self.modular_llm_game_name:
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
            self.game_name, self.slots, self.cat_slots, self.noncat_slots
        )
        self.dbquery = DBQueryBuilder(
            self.domain,
            self.domaindbpath,
            self.domainschema,
            self.cat_slots,
            self.noncat_slots,
            self.similarity["threshold"],
        )

        if self.game_name == self.modular_llm_game_name:
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
        if self.success:
            action = {
                "type": "info",
                "content": "game is successful, all the slots matched",
            }
        elif self.lose:
            if self.misses:
                action = {
                    "type": "info",
                    "content": "lost game, mismatch in some/all the slots"
                    + "\n"
                    + json.dumps(self.misses),
                }
            else:
                action = {
                    "type": "info",
                    "content": f"lost game, max turns ({self.n_turns}) reached",
                }
        elif self.aborted:
            action = {
                "type": "info",
                "content": "game is aborted, response is not valid",
            }
        else:
            action = {
                "type": "info",
                "content": f"lost game, max turns ({self.n_turns}) reached",
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
        answer_a = self._get_utterance("a")
        logger.error(f"Player A answer\n{answer_a}")

        # check if the game should be aborted or lost
        is_valid_turn, details = self._check_validity("a", answer_a)
        # print(f"2. Check Validity: is_valid_turn:{is_valid_turn}, details: {details}")
        logger.error(
            f"Player A Check Validity: is_valid_turn:{is_valid_turn}, details: {details}"
        )
        if not is_valid_turn:
            # stop game
            return None

        if self.success or self.lose:
            return None

        # add A's reply to B's history
        logger.error(f"Appended Player A answer to PlayerB\n{details}")
        self._append_utterance(details, "b", "user")
        # also add the reply to the transcript
        action = {
            "type": "send message",
            "content": self.player_b.history[-1]["content"],
        }
        self.log_event(from_="GM", to="Player 2", action=action)

        # now do the same for player B
        is_valid_turn, details = self._handle_playerb_response()

        if not is_valid_turn:
            # stop game
            return None

        # add B's reply to A's history
        # check if it is DB query, then no need to append to the player a's history
        if not self._isdbquery(is_valid_turn):
            logger.error(f"Appended Player B answer to PlayerA\n{details}")
            self._append_utterance(details, "a", "user")
            # also add the reply to the transcript
            action = {
                "type": "send message",
                "content": self.player_a.history[-1]["content"],
            }
            self.log_event(from_="GM", to="Player 1", action=action)

            self.complete_turns += 1
        else:
            self._handle_dbquery(details)




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
                prompt, raw_answer, answer = self.player_b(
                    self.player_b.history, self.current_turn
                )
                answer = cleanupanswer(answer)

                # add reply to its own memory
                self._append_utterance(answer, "b", "assistant")

            elif self.game_name == self.modular_llm_game_name:
                prompt, raw_answer, answer = self.modularb.run(self.current_turn)
                # Don't add answer to player b's history, as it is already added in the modularb.run method

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
        logger.error(
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
                if self.current_turn == 1:
                    #TODO: check for cases, where player_b.history is empty
                    self.player_b.history[-1]["content"] += content
                else:
                    if isinstance(utterance, dict):
                        b_response = json.dumps(utterance)
                    else:
                        b_response = utterance

                    if role == "user":
                        turn_prompt = self.turn_prompt_player_b
                    elif role == "db-query":
                        turn_prompt = self.dbquery_prompt_player_b

                    self.player_b.history.append({"role": "user", "content": turn_prompt + "\n\n" + b_response})

    def _check_validity(self, player: str, answer: str) -> bool:
        """Check if answer is valid and correct (firstlast specific)."""
        # parse answer
        response, details = self.parse(player, answer)
        # print(f"Check Validity: isdone:{isdone}, details: {details}")
        logger.error(
            f"Check Validity: player: {player}, response: {response} details: {details}"
        )

        if response is None:
            self.aborted = True
            # log the abortion event
            action = {"type": "invalid format", "content": "abort"}
            self.log_event(from_="GM", to="GM", action=action)
            # increase the counter of requests that violate form rules
            self.violated_request_counts[self.current_turn] += 1
            return False, None

        # increase the counter of requests that conform to form rules
        self.parsed_request_counts[self.current_turn] += 1
        # log the event that the string was valid (no strange characters)
        action = {"type": "metadata", "content": "response confirms to rules"}
        self.log_event(from_="GM", to="GM", action=action)

        if player == "a":
            result = response
            if "done" in response:
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
            result = details

            # is db query?
            if self._isdbquery(response):
                self._handle_dbquery(details)

            else:
                # is booking completed?
                is_booking_done = self._check_bookingstatus(response, details)

                # log the fact that the booking is completed
                if is_booking_done:
                    action = {"type": "parse", "content": f"booking completed"}
                    self.log_event(from_="GM", to="GM", action=action)

        return True, result

    def _check_bookingstatus(self, response, details) -> bool:
        if response == "booking-confirmed" and isinstance(details, dict):
            self.slots_gen = details
            logger.error(f"Saved slots_gen: {self.slots_gen}")
            return True
        return False
    
    def _isdbquery(self, status) -> bool:
        if isinstance(status, str) and status == "db-query":
            return True
        return False
    
    def _handle_playerb_response(self) -> Tuple[bool, str]:
        # get player B's reply and add it to its history
        answer_b = self._get_utterance("b")
        # print(f"3. Player B answer\n{answer_b}")
        logger.error(f"Player B answer\n{answer_b}")
        # check if the game should be aborted or lost
        is_valid_turn, details = self._check_validity("b", answer_b)
        logger.error(
            f"Player B Check Validity: is_valid_turn:{is_valid_turn}, details: {details}"
        )
        return is_valid_turn, details


    def _handle_dbquery(self, details) -> bool:

        while True:
            slots = details
            dbresult = self.dbquery.run(slots)
            message = f'{self.statusmsg[dbresult["status"]]} {self.statusmsg["dbfetch"]}\n'
            if dbresult["status"] == "success":
                message += json.dumps(dbresult["data"])
            else:
                message += dbresult["error"]
            
            self._append_utterance(message, "b", "db-query")
            is_valid_turn, details = self._handle_playerb_response()
            if not is_valid_turn:
                return False
            if not self._isdbquery(details):
                break


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
        pass


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
