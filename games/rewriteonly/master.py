import copy
from typing import List, Dict, Tuple
from string import ascii_lowercase as letters
from collections import Counter

import numpy as np

import clemgame.metrics as ms
from clemgame.clemgame import GameMaster, GameBenchmark
from clemgame import get_logger

from games.rewriteonly.players import InstructionGiver
from games.rewriteonly.instancegenerator import GAME_NAME

# use the framework logger to log events relevant at runtime;
# this is independent from the game records / transcript
logger = get_logger(__name__)


class ReWriteOnly(GameMaster):
    """Implement mechanisms for playing FirstLast."""

    def __init__(self, experiment: Dict, player_backends: List[str]):
        super().__init__(GAME_NAME, experiment, player_backends)

        # save experiment and player attributes that will be necessary later
        self.test = experiment["name"]
        self.model_a = player_backends[0]

        # initialise attributes that will be used for the evaluation scores
        self.aborted: bool = False
        self.lose: bool = False
        self.complete_turns: int = 0

    def setup(
        self,
        n_turns: int,
        prompt_player_a: str,
        game_id: int,
        dialogue: List,
    ) -> None:
        """Setup the episode (mandatory)."""
        self.n_turns = n_turns
        self.game_id = game_id
        self.dialogue = dialogue

        # instantiate both players
        self.player_a = InstructionGiver(self.model_a, "A")

        # initialise game variables
        self.current_turn: int = 0
        # self.current_letter: str = first_letter

        # initialise common metrics
        self.request_counts = [0] * (n_turns + 1)
        self.parsed_request_counts = [0] * (n_turns + 1)
        self.violated_request_counts = [0] * (n_turns + 1)

        self.game_data = {
            "utterance": {"before": [], "after": []}
        }

        # add initial prompts to each player's messages
        self.initiate(prompt_player_a)

        # always log the details of the players in this format (see logdoc)
        self.log_players(
            {
                "GM": "Game master for Minecraft",
                "Player 1": f"Player A: {self.model_a}",
                "Player 2": f"Player B: Programmatic",
            }
        )

        # log any additional keys that will be relevant for evaluation
        self.log_key("n_turns", n_turns)

    def play(self) -> None:
        """Play the game until the end (mandatory)."""
        # play the game
        while self.proceed():
            self.current_turn += 1
            # always call log_next_turn when a new turn starts
            self.log_next_turn()
            self.turn()

        if self.complete_turns == self.n_turns:
            # log a message informing that the game was successfuly played
            action = {"type": "info", "content": "game successful"}
            self.log_event(from_="GM", to="GM", action=action)

        action = {'type': 'final_prompt_a', 'content': self.player_a.history}
        self.log_event(from_='GM', to='GM', action=action)

        action = {'type': 'resforeval', 'content': self.game_data}
        self.log_event(from_='GM', to='GM', action=action)

        # log a final message saying that the game did came to an end
        action = {"type": "info", "content": "end game"}
        self.log_event(from_="GM", to="GM", action=action)
        # log all temporary game variables that are needed for evaluation
        self.log_eval_assets()

    def _yield_prompt(self, dialogues: List) -> Tuple[str, str]:
        for dialogue in dialogues:
            yield dialogue["utterance"], dialogue["action"]

    def _add_instruction(self, player: str, utterance: str, prompt: dict) -> None:
        content = "Instruction\n" + utterance + "\n"
        if prompt[-1]["role"] == "user":
            prompt[-1]["content"] = prompt[-1]["content"] + "\n" + content
        else:
            if player == 'a':
                self.player_a.history.append({"role": "user", "content": content})

        return content

    def initiate(self, prompt_player_a: str) -> None:
        """Initialise the dialogue history (minecraft specific)."""
        # always call log_next_turn what a turn starts
        self.log_next_turn()

        # append the initial message of each player to their history
        # the value user means the message is from an interlocutor of the model
        self.player_a.history.append({"role": "user", "content": prompt_player_a})

        # also log the messages as events for the transcriptions
        # action = {'type': 'send message', 'content': prompt_player_a}
        # self.log_event(from_='GM', to='Player 1', action=action)

        self.dialogue_turns = self._yield_prompt(self.dialogue)
        """
        utterance, action = next(self.dialogue_turns)
        self.player_a.history[-1]["content"] += "\Instruction\n" + utterance + "\n"
        self.game_data["utterance"]["before"].append(utterance)
        self.game_data["action"]["groundtruth"].append(action)
        """

        # action = {'type': 'send message', 'content': prompt_player_b}
        # self.log_event(from_='GM', to='Player 2', action=action)
        # self.player_b.history[-1]["content"] += "\Instruction\n" + utterance + "\n"

    def proceed(self) -> None:
        """Check if the game loop should continue (firstlast specific)."""
        return self.current_turn < self.n_turns and not self.aborted and not self.lose

    def turn(self) -> None:
        """Perform a game turn, utterances by A and B (firstlast specific)."""
        # get player A's reply and add it to its history
        # print(f"Inside turn {self.current_turn}, calling _get_utterance")
        answer_a = self._get_utterance("a")

        # check if the game should be aborted or lost
        is_valid_turn = self._check_validity("a", answer_a)
        if not is_valid_turn:
            # stop game
            return None

        # add A's reply to B's history
        # self._append_utterance(answer_a, 'b', 'user')
        # also add the reply to the transcript
        #action = {"type": "send message", "content": answer_a}

        self.complete_turns += 1

    def _append_utterance(self, utterance: str, player: str, role: str) -> None:
        """Add an utterance to the history of a player (firstlast specific)."""
        assert player in ("a", "b")
        if player == "a":
            self.player_a.history.append({"role": role, "content": utterance})

    def _get_utterance(self, player: str) -> str:
        """Get utterance from a player and log it (firstlast specific)."""
        assert player in ("a", "b")
        if player == "a":
            # print("Inside _get_utterance, calling _yield_prompt")
            utterance, action = next(self.dialogue_turns)
            action = " ".join(action)
            # print("Got utterance and action from _yield_prompt")
            # self.game_data["utterance"].append(utterance)
            self.game_data["utterance"]["before"].append(utterance)

            content = self._add_instruction('a', utterance, self.player_a.history)

            # print("Calling api wrapper for player a")
            if self.current_turn == 1:
                action = {
                    "type": "send message",
                    "content": self.player_a.history[-1]["content"],
                }
            else:
                action = {"type": "send message", "content": content}

            self.log_event(from_="GM", to="Player 1", action=action)

            # make an API call (or get a programmatic response) from player a
            prompt, raw_answer, answer = self.player_a(
                self.player_a.history, self.current_turn
            )
            # add reply to its own memory
            self._append_utterance(answer, "a", "assistant")
            # also add reply to the records
            action = {"type": "get message", "content": answer}
            self.log_event(
                from_="Player 1",
                to="GM",
                action=action,
                call=(copy.deepcopy(prompt), raw_answer),
            )

        # increase the number of API requests
        self.request_counts[self.current_turn] += 1
        return answer

    def check_correctness(self, answer: str) -> bool:
        """Check if the utterance conforms to rules (firstlast specific)."""
        # Check if the answer contains commands other than pick and place
        return True

    def parse(self, player: str, response: str) -> dict:
        # print(f"Inside parse: response = {response}")
        """Check if utterance is valid and contains defined labels."""
        answer = ""

        if player == "a":
            label_to_check = "Rewrite"

        if label_to_check in response:
            answer = response.split(label_to_check)[1].strip()
            answer = answer.split("\n")
            answer = " ".join(answer)
        else:
            print(f"Label {label_to_check} not found in response {response}")
            return None

        print(f"Inside parse: answer = {answer} turn = {self.current_turn}")
        return answer

    def _check_validity(self, player: str, answer: str) -> bool:
        """Check if answer is valid and correct (firstlast specific)."""
        # print("Inside _check_validity, calling parse()")
        # parse answer
        answer = self.parse(player, answer)

        # if invalid tag, abort game
        if answer is None:
            self.aborted = True
            # log the abortion event
            action = {"type": "invalid format", "content": "abort"}
            self.log_event(from_="GM", to="GM", action=action)
            # increase the counter of requests that violate form rules
            self.violated_request_counts[self.current_turn] += 1
            return False

        if player == "a":
            self.game_data["utterance"]["after"].append(answer)

        # increase the counter of requests that conform to form rules
        self.parsed_request_counts[self.current_turn] += 1
        # log the event that the string was valid (no strange characters)
        action = {"type": "metadata", "content": "valid string"}
        self.log_event(from_="GM", to="GM", action=action)

        # if correct characters, check correctness wrt game rules
        is_correct_reply = self.check_correctness(answer)

        # if not correct, lost game
        if not is_correct_reply:
            self.lose = True
            # log the fact that the game is now lost
            action = {"type": "parse", "content": f"{answer} violates rules"}
            self.log_event(from_="GM", to="GM", action=action)

            return False

        # log the fact that the answer was correct
        action = {"type": "parse", "content": f"{answer} conforms to rules"}
        self.log_event(from_="GM", to="GM", action=action)

        return True

    def compute_scores(self, episode_interactions: Dict) -> None:
        """Compute episode-level and turn-level scores (mandatory)."""
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


    def log_eval_assets(self) -> None:
        """Aux to log variables needed for scoring (firstlast specific)"""
        self.log_key("Played turns", self.current_turn)
        self.log_key("Complete turns", self.complete_turns)
        self.log_key(ms.METRIC_ABORTED, self.aborted)
        self.log_key(ms.METRIC_LOSE, self.lose)
        self.log_key(ms.METRIC_REQUEST_COUNT, self.request_counts)
        self.log_key(ms.METRIC_REQUEST_COUNT_PARSED, self.parsed_request_counts)
        self.log_key(ms.METRIC_REQUEST_COUNT_VIOLATED, self.violated_request_counts)


class RewriteOnlyGameBenchmark(GameBenchmark):
    """Integrate the game into the benchmark run."""

    def __init__(self):
        super().__init__(GAME_NAME)

    # defines whether the game is single player or not
    def is_single_player(self):
        return True

    # add a description of your game
    def get_description(self):
        return "A simple game to generate code for the given instruction."

    # copy this, replacing the name of the game master in the return statement
    def create_game_master(
        self, experiment: Dict, player_backends: List[str]
    ) -> GameMaster:
        return ReWriteOnly(experiment, player_backends)
