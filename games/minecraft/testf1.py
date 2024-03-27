# save the contents of this cell as games/firstlast/master.py

import copy
from typing import List, Dict, Tuple
from string import ascii_lowercase as letters

import numpy as np

import clemgame.metrics as ms
from clemgame.clemgame import GameMaster, GameBenchmark
from clemgame import get_logger

from games.firstlast.players import Speaker
from games.firstlast.instancegenerator import GAME_NAME


# use the framework logger to log events relevant at runtime;
# this is independent from the game records / transcript
logger = get_logger(__name__)


class FirstLast(GameMaster):
    """Implement mechanisms for playing FirstLast."""
    def __init__(self, experiment: Dict, player_backends: List[str]):
        super().__init__(GAME_NAME, experiment, player_backends)

        # save experiment and player attributes that will be necessary later
        self.topic = experiment['name']
        self.model_a = player_backends[0]
        self.model_b = player_backends[1]

        # initialise attributes that will be used for the evaluation scores
        self.aborted: bool = False
        self.lose: bool = False
        self.complete_turns: int = 0

    def setup(self, first_letter: str, n_turns: int, prompt_player_a: str,
              prompt_player_b: str, game_id: int) -> None:
        """Setup the episode (mandatory)."""

        self.n_turns = n_turns

        # instantiate both players
        self.player_a = Speaker(self.model_a, 'A', first_letter)
        self.player_b = Speaker(self.model_b, 'B', first_letter)

        # initialise game variables
        self.current_turn: int = 0
        self.current_letter: str = first_letter

        # initialise common metrics
        self.request_counts = [0] * (n_turns + 1)
        self.parsed_request_counts = [0] * (n_turns + 1)
        self.violated_request_counts = [0] * (n_turns + 1)

        # add initial prompts to each player's messages
        self.initiate(prompt_player_a, prompt_player_b)

        # always log the details of the players in this format (see logdoc)
        self.log_players({
            'GM': 'Game master for FirstLast',
            'Player 1': f'Player A: {self.model_a}',
            'Player 2': f'Player B: {self.model_b}'
            })

        # log any additional keys that will be relevant for evaluation
        self.log_key('n_turns', n_turns)
        
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
            action = {'type': 'info', 'content': 'game successful'}
            self.log_event(from_='GM', to='GM', action=action)

        # log a final message saying that the game did came to an end
        action = {'type': 'info', 'content': 'end game'}
        self.log_event(from_='GM', to='GM', action=action)
        # log all temporary game variables that are needed for evaluation
        self.log_eval_assets()


    def initiate(self, prompt_player_a: str, prompt_player_b: str) -> None:
        """Initialise the dialogue history (firstlast specific)."""
        # always call log_next_turn what a turn starts
        self.log_next_turn()

        # append the initial message of each player to their history
        # the value user means the message is from an interlocutor of the model
        self.player_a.history.append({'role': 'user', 'content': prompt_player_a})
        self.player_b.history.append({'role': 'user', 'content': prompt_player_b})

        # also log the messages as events for the transcriptions
        action = {'type': 'send message', 'content': prompt_player_a}
        self.log_event(from_='GM', to='Player 1', action=action)
        action = {'type': 'send message', 'content': prompt_player_b}
        self.log_event(from_='GM', to='Player 2', action=action)

    def proceed(self) -> None:
        """Check if the game loop should continue (firstlast specific)."""
        return (self.current_turn < self.n_turns
                and not self.aborted
                and not self.lose)

    def update_letter(self) -> None:
        """Update the letter being played (firstlast specific)."""
        current_index = letters.index(self.current_letter)
        self.current_letter = letters[current_index + 1]

    def _get_utterance(self, player: str) -> str:
        """Get utterance from a player and log it (firstlast specific)."""
        assert player in ('a', 'b')
        if player == 'a':
            # make an API call (or get a programmatic response) from player a
            prompt, raw_answer, answer = self.player_a(self.player_a.history,
                                                    self.current_turn)
            # add reply to its own memory
            self._append_utterance(answer, 'a', 'assistant')
            # also add reply to the records
            action = {'type': 'get message', 'content': answer}
            self.log_event(from_='Player 1', to='GM', action=action,
                        call=(copy.deepcopy(prompt), raw_answer))
        else:
            # make an API call (or get a programmatic response) from player b
            prompt, raw_answer, answer = self.player_b(self.player_b.history,
                                            self.current_turn)
            # add reply to its own memory
            self._append_utterance(answer, 'b', 'assistant')
            # aldo add reply to the records
            action = {'type': 'get message', 'content': answer}
            self.log_event(from_='Player 2', to='GM', action=action,
                        call=(copy.deepcopy(prompt), raw_answer))
        # increase the number of API requests 
        self.request_counts[self.current_turn] += 1
        return answer

    def _check_validity(self, answer: str) -> bool:
        """Check if answer is valid and correct (firstlast specific)."""
        # parse answer
        first_token, last_token = self.parse(answer)

        # if invalid tag, abort game
        if first_token is None or last_token is None:
            self.aborted = True
            # log the abortion event
            action = {'type': 'invalid format', 'content': 'abort'}
            self.log_event(from_='GM', to='GM', action=action)
            # increase the counter of requests that violate form rules
            self.violated_request_counts[self.current_turn] += 1
            return False

        # increase the counter of requests that conform to form rules
        self.parsed_request_counts[self.current_turn] += 1
        # log the event that the string was valid (no strange characters)
        action = {'type': 'metadata', 'content': 'valid string'}
        self.log_event(from_='GM', to='GM', action=action)

        # if correct characters, check correctness wrt game rules
        is_correct_reply = self.check_correctness(first_token, last_token)

        # if not correct, lost game
        if not is_correct_reply:
            self.lose = True
            # log the fact that the game is now lost
            action = {'type': 'parse',
                      'content': f'{first_token}/{last_token} violates rules'}
            self.log_event(from_='GM', to='GM', action=action)

            return False

        # log the fact that the answer was correct
        action = {'type': 'parse',
                  'content': f'{first_token}/{last_token} conforms to rules'}
        self.log_event(from_='GM', to='GM', action=action)

        return True

    def turn(self) -> None:
        """Perform a game turn, utterances by A and B (firstlast specific)."""
        # get player A's reply and add it to its history
        answer_a = self._get_utterance('a')

        # check if the game should be aborted or lost
        is_valid_turn = self._check_validity(answer_a)
        if not is_valid_turn:
            # stop game
            return None

        # add A's reply to B's history
        self._append_utterance(answer_a, 'b', 'user')
        # also add the reply to the transcript
        action = {'type': 'send message', 'content': answer_a}
        self.log_event(from_='GM', to='Player 2', action=action)

        # next player gets the next letter in the alphabet
        self.update_letter()

        # now do the same for player B

        # get player B's reply and add it to its history
        answer_b = self._get_utterance('b')

        # check if the game should be aborted or lost
        is_valid_turn = self._check_validity(answer_b)
        if not is_valid_turn:
            # stop game
            return None

        # add B's reply to A's history
        self._append_utterance(answer_b, 'a', 'user')
        # also add the reply to the transcript
        action = {'type': 'send message', 'content': answer_b}
        self.log_event(from_='GM', to='Player 1', action=action)

        self.update_letter()
        self.complete_turns += 1

    def _append_utterance(self, utterance: str, player: str, role: str) -> None:
        """Add an utterance to the history of a player (firstlast specific)."""
        assert player in ('a', 'b')
        if player == 'a':
            self.player_a.history.append({'role': role, 'content': utterance})
        else:
            self.player_b.history.append({'role': role, 'content': utterance})

    @staticmethod
    def parse(utterance: str) -> Tuple[str, str]:
        """Check if utterance is valid and return first/last tokens (firstlast specific)."""
        if not utterance.startswith('I SAY: '):
            return None, None
        tokens = utterance[7:].split()
        return tokens[0], tokens[-1]
            
    def check_correctness(self, first_token: str, last_token: str) -> bool:
        """Check if the utterance conforms to rules (firstlast specific)."""
        return first_token[0] == self.current_letter and first_token[0] == last_token[0]

    def compute_scores(self, episode_interactions: Dict) -> None:
        """Compute episode-level and turn-level scores (mandatory)."""
        played_turns = episode_interactions['Played turns']
        complete_turns = episode_interactions['Complete turns']
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
        success =  1 - lose if not aborted else 0
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
        self.log_key('Played turns', self.current_turn)
        self.log_key('Complete turns', self.complete_turns)
        self.log_key(ms.METRIC_ABORTED, self.aborted)
        self.log_key(ms.METRIC_LOSE, self.lose)
        self.log_key(ms.METRIC_REQUEST_COUNT, self.request_counts)
        self.log_key(ms.METRIC_REQUEST_COUNT_PARSED, self.parsed_request_counts)
        self.log_key(ms.METRIC_REQUEST_COUNT_VIOLATED, self.violated_request_counts)