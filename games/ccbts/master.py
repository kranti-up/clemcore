import copy
from typing import List, Dict, Tuple
from string import ascii_lowercase as letters
from collections import Counter

import numpy as np

import clemgame.metrics as ms
from clemgame.clemgame import GameMaster, GameBenchmark
from clemgame import get_logger

from games.ccbts.players import InstructionGiver
from games.ccbts.instancegenerator import GAME_NAME

from games.ccbts.utils.ccbtseval import CCBTSEval


# use the framework logger to log events relevant at runtime;
# this is independent from the game records / transcript
logger = get_logger(__name__)


class CCBTS(GameMaster):
    """Implement mechanisms for playing FirstLast."""
    def __init__(self, experiment: Dict, player_backends: List[str]):
        super().__init__(GAME_NAME, experiment, player_backends)

        # save experiment and player attributes that will be necessary later
        self.test = experiment['name']
        self.model_a = player_backends[0]

        # initialise attributes that will be used for the evaluation scores
        self.aborted: bool = False
        self.lose: bool = False
        self.complete_turns: int = 0

        self.ccbtseval = CCBTSEval()


    def setup(self, n_turns: int, prompt: str, game_id: int,
              dialogues: list,
              rows: int, cols: int,
              output_labels: dict) -> None:
        """Setup the episode (mandatory)."""
        self.n_turns = n_turns
        self.game_id = game_id

        self.dialogues = dialogues
        self.output_labels = output_labels

        # instantiate both players
        self.player_a = InstructionGiver(self.model_a, "A")

        # initialise game variables
        self.current_turn: int = 0
        #self.current_letter: str = first_letter

        # initialise common metrics
        self.request_counts = [0] * (n_turns + 1)
        self.parsed_request_counts = [0] * (n_turns + 1)
        self.violated_request_counts = [0] * (n_turns + 1)

        self.game_data = {"instruction": {}, "action": {"groundtruth":{}, "prediction": {}}}
        self.rows = rows
        self.cols = cols

        # add initial prompts to each player's messages
        self.initiate(prompt)

        # always log the details of the players in this format (see logdoc)
        self.log_players({
            'GM': 'Game master for CCBTS',
            'Player 1': f'Player A: {self.model_a}',
            'Player 2': f'Player B: Code Evaluator (Programmatic)'
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
        #action = {'type': 'all turn prompt', 'content': "look into interactions file", "data": self.player_a.history}
        #self.log_event(from_='GM', to='GM', action=action)

        #action = {'type': 'metadata', 'content': "", "evaluation":self.game_data}
        #self.log_event(from_='GM', to='GM', action=action)

        # log a final message saying that the game did came to an end
        action = {'type': 'info', 'content': 'end game'}
        self.log_event(from_='GM', to='GM', action=action)
        # log all temporary game variables that are needed for evaluation
        self.log_eval_assets()

    def _yield_prompt(self, dialogues: List) -> Tuple[str, str]:
        for dialogue in dialogues:
            yield dialogue["<Programmer>"], dialogue["<Editor>"]


    def initiate(self, prompt_player_a: str) -> None:
        """Initialise the dialogue history (firstlast specific)."""
        # always call log_next_turn what a turn starts
        self.log_next_turn()

        # append the initial message of each player to their history
        # the value user means the message is from an interlocutor of the model
        self.player_a.history.append({'role': 'user', 'content': prompt_player_a})

        # also log the messages as events for the transcriptions
        #action = {'type': 'send message', 'content': prompt_player_a}
        #self.log_event(from_='GM', to='Player 1', action=action)
        self.dialogue_turns = self._yield_prompt(self.dialogues)

    def proceed(self) -> None:
        """Check if the game loop should continue (firstlast specific)."""
        return (self.current_turn < self.n_turns
                and not self.aborted
                and not self.lose)


    def _add_instruction(self, instruction: str, prompt: dict) -> None:
        content = "Instruction\n" + instruction + "\n"
        if prompt[-1]["role"] == "user":
            prompt[-1]["content"] = prompt[-1]["content"] + "\n" + content
        else:
            self.player_a.history.append({'role': "user", 'content': content})  

        return content
    
    def _append_utterance(self, utterance: str, player: str, role: str) -> None:
        """Add an utterance to the history of a player (firstlast specific)."""
        assert player in ('a', 'b')
        if player == 'a':
            self.player_a.history.append({'role': role, 'content': utterance})      

    def _get_code(self, player: str) -> str:
        """Get utterance from a player and log it (firstlast specific)."""
        assert player in ('a')

        instruction, groundtruth = next(self.dialogue_turns)

        self.game_data["instruction"][self.current_turn] = instruction
        self.game_data["action"]["groundtruth"][self.current_turn] = {}
        if isinstance(groundtruth, str):
            self.game_data["action"]["groundtruth"][self.current_turn]["output"] = groundtruth

        else:
            self.game_data["action"]["groundtruth"][self.current_turn].update(groundtruth)


        content = self._add_instruction(instruction, self.player_a.history)

        action_content = content if self.current_turn != 1 else self.player_a.history[-1]["content"]
        action = {'type': 'send message', 'content': action_content}

        self.log_event(from_='GM', to='Player 1', action=action)

        # make an API call (or get a programmatic response) from player a
        prompt, raw_answer, answer = self.player_a(self.player_a.history,
                                                self.current_turn)

        # add reply to its own memory
        self._append_utterance(answer, 'a', 'assistant')

        # also add reply to the records
        action = {'type': 'get message', 'content': answer}
        self.log_event(from_='Player 1', to='GM', action=action,
                    call=(copy.deepcopy(prompt), raw_answer))

        # increase the number of API requests 
        self.request_counts[self.current_turn] += 1
        return answer

    def _check_validity(self, answer: str) -> bool:
        """Check if answer is valid and correct (firstlast specific)."""
        # parse answer
        answer = self.parse(answer)
        if answer is None:
            self.aborted = True
            # log the abortion event
            action = {'type': 'invalid format', 'content': 'abort'}
            self.log_event(from_='GM', to='GM', action=action)
            # increase the counter of requests that violate form rules
            self.violated_request_counts[self.current_turn] += 1
            return False

        self.game_data["action"]["prediction"][self.current_turn] = {}
        self.game_data["action"]["prediction"][self.current_turn].update(answer)


        # increase the counter of requests that conform to form rules
        self.parsed_request_counts[self.current_turn] += 1
        # log the event that the string was valid (no strange characters)
        #log_data = {"ground_truth": self.game_data[self.current_turn]["ground_truth"],
        #           "prediction": self.game_data[self.current_turn]["prediction"]}

        action = {'type': 'metadata', 'content': answer}
        self.log_event(from_='GM', to='GM', action=action)


        # log the fact that the answer was correct
        action = {'type': 'parse',
                  #'content': f'{answer} confirms to rules'}
                  'content': 'answer confirms to rules'}
        self.log_event(from_='GM', to='GM', action=action)

        return True

    def turn(self) -> None:
        """Perform a game turn, utterances by A and B (firstlast specific)."""

        # get player A's reply and add it to its history
        answer_a = self._get_code('a')

        # check if the game should be aborted or lost
        is_valid_turn = self._check_validity(answer_a)
        if not is_valid_turn:
            # stop game
            return None

        self.complete_turns += 1 


    def parse(self, response: str) -> dict:
        #print(f"Inside parse: response = {response}")
        """Check if utterance is valid and contains defined labels."""
        try:
            answer = {label: response.split(value)[1].strip() if value in response else None
                    for label, value in self.output_labels.items() if value is not None}

            if None in answer.values():
                missing_labels = [label for label, result in answer.items() if result is None]
                print(f"Labels {missing_labels} not found in response: {response}")
                return None

            print(f"Inside parse: answer = {answer}")
            return answer
        except Exception as e:
            print(f"An error occurred while parsing the answer: {e}")
            return None
    
    def check_correctness(self, first_token: str, last_token: str) -> bool:
        """Check if the utterance conforms to rules (firstlast specific)."""
        return first_token[0] == self.current_letter and first_token[0] == last_token[0]    
            

    def compute_scores(self, episode_interactions: Dict) -> None:
        """Compute episode-level and turn-level scores (mandatory)."""

        #turn_scores = {turn: {'exact_match': 'failure', 'codebleu': 'failure', 'exec_score': 'failure'} for turn in range(1, self.n_turns+1)}
        #episode_scores = {metric: {"precision": 0.0, "recall": 0.0, "f1_score": 0.0} for metric in ["exact_match", "codebleu", "exec_score"]}

        #if not episode_interactions[ms.METRIC_ABORTED]:
        results = episode_interactions["Evaluation"]
        if results:
            turn_scores, episode_scores = self.ccbtseval.parse_results(self.rows, self.cols, results)

        for score in episode_scores:
            self.log_episode_score(score, episode_scores[score])

        for metric in ["exact_match", "codebleu", "exec_score"]:
            for turn in turn_scores:
                self.log_turn_score(int(turn)-1, metric, turn_scores[turn][metric])


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
        self.log_key('Evaluation', self.game_data)

class CCBTSGameBenchmark(GameBenchmark):
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
    def create_game_master(self,
                           experiment: Dict,
                           player_backends: List[str]
                           ) -> GameMaster:
        return CCBTS(experiment, player_backends)