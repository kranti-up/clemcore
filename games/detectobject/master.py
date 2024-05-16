import copy
from typing import List, Dict, Tuple
from string import ascii_lowercase as letters
import re
from collections import Counter

import numpy as np

import clemgame.metrics as ms
from clemgame.clemgame import GameMaster, GameBenchmark, GameScorer
from clemgame import get_logger

from games.detectobject.players import InstructionGiver
from games.detectobject.instancegenerator import GAME_NAME
from games.detectobject.utils.objdetecteval import ObjDetectEvaluator




# use the framework logger to log events relevant at runtime;
# this is independent from the game records / transcript
logger = get_logger(__name__)


class DetectObject(GameMaster):
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


    def setup(self, n_turns: int, prompt: str, game_id: int,
              dialogue_data: dict) -> None:
        """Setup the episode (mandatory)."""
        self.n_turns = n_turns
        self.game_id = game_id

        self.dialogue_data = dialogue_data

        # instantiate both players
        self.player_a = InstructionGiver(self.model_a)

        # initialise game variables
        self.current_turn: int = 0

        # initialise common metrics
        self.request_counts = [0] * (n_turns + 1)
        self.parsed_request_counts = [0] * (n_turns + 1)
        self.violated_request_counts = [0] * (n_turns + 1)

        self.game_result = {}

        # add initial prompts to each player's messages
        self.initiate(prompt)

        # always log the details of the players in this format (see logdoc)
        self.log_players({
            'GM': 'Game master for GenInsta',
            'Player 1': f'Player A: {self.model_a}',
            'Player 2': f'Player B: ObjectID Evaluator (Programmatic)'
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
            action = {'type': 'info', 'content': 'dialogue completed'}
            self.log_event(from_='GM', to='GM', action=action)

        # log a final message saying that the game did came to an end
        action = {'type': 'info', 'content': 'end game'}
        self.log_event(from_='GM', to='GM', action=action)
        # log all temporary game variables that are needed for evaluation
        self.log_eval_assets()

    def initiate(self, prompt_player_a: str) -> None:
        """Initialise the dialogue history (firstlast specific)."""
        # always call log_next_turn what a turn starts
        self.log_next_turn()

        #self.dialogue_turns = self._yield_conversation()

        # append the initial message of each player to their history
        # the value user means the message is from an interlocutor of the model
        self.player_a.history.append({'role': 'user', 'content': prompt_player_a})

    def proceed(self) -> None:
        """Check if the game loop should continue (firstlast specific)."""
        return (self.current_turn < self.n_turns
                and not self.aborted
                and not self.lose)
    
    def parse(self, response: str) -> dict:
        answer = re.findall(r'\d+', response)

        # Convert the strings to integers
        answer = [int(num) for num in answer]

        print(f"Inside parse: answer = {answer}")
        return answer     


    def parse_old(self, response: str) -> dict:
        """
        Not doing strict label checking
        The response is expected to be in the format:
        ObjectID\n
        <objectid 1>\n
        <objectid 2>\n
        ...

        Strip the label and get the detected object ids
        Sometimes model response may not have the label, in that case, return the response as it is
        """
        
        def clean_id(obj_id):
            return obj_id.translate(str.maketrans("", "", ": \t.")).strip()

        response = response.strip().lower()
        labels = ["objectid", "object id"]

        for label in labels:
            if label in response:
                response = response.split(label)[1].strip()
                response = response.split("\n")
                if response[0] in ["", " ", ":", "\t", "\n", ".", ","]:
                    response = response[1:]

        cleaned_ids = []
        for obj_id in response:
            # Split on commas in case multiple IDs are on the same line
            for sub_id in obj_id.split(','):
                cleaned = clean_id(sub_id)
                try:
                    # Attempt to convert cleaned IDs to integers
                    cleaned_ids.append(int(cleaned))
                except ValueError:
                    print(f"Warning: Unable to convert '{cleaned}' to integer.")

        if cleaned_ids:  
            answer = cleaned_ids

        else:
            answer = response

        print(f"Inside parse: answer = {answer}")        
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

        #TODO: Save the model response for evaluation
        self.game_result[self.current_turn]["prediction"] = answer

        # increase the counter of requests that conform to form rules
        self.parsed_request_counts[self.current_turn] += 1

        action = {'type': 'metadata', 'content': {"prediction": answer,
                                                   "groundtruth": self.game_result[self.current_turn]["groundtruth"]}}
        self.log_event(from_='GM', to='GM', action=action)


        # log the fact that the answer was correct
        '''
        action = {'type': 'parse',
                  #'content': f'{answer} confirms to rules'}
                  'content': 'answer confirms to rules'}
        self.log_event(from_='GM', to='GM', action=action)
        '''

        return True
    
    def _yield_conversation(self):
        for turn in self.dialogue_data["total_dialogues"]:
            yield turn["uapairs"], turn["groundtruth"]


    def _add_instruction(self, conversation: str, prompt: dict) -> None:
        content = ""
        for conv in conversation:
            content += "\n".join(conv) + "\n"

        if prompt[-1]["role"] == "user":
            prompt[-1]["content"] = prompt[-1]["content"] + "\n" + content
        else:
            self.player_a.history.append({'role': "user", 'content': content})  

        return content

    def _get_instructions(self, player: str) -> str:
        """Get utterance from a player and log it (firstlast specific)."""
        assert player in ('a')

        #dialogue, groundtruth = next(self.dialogue_turns)
        utterance = self.dialogue_data["utterance"]
        groundtruth = self.dialogue_data["groundtruth"]

        add_data = {} #TODO: Add the data to be added
        content = self._add_instruction(utterance, self.player_a.history)
        
        #TODO: Add ground truth information to result for evaluation purposes
        self.game_result[self.current_turn] = {"utterance": utterance, "groundtruth": groundtruth}

        action_content = content if self.current_turn != 1 else self.player_a.history[-1]["content"]
        action = {'type': 'send message', 'content': action_content}

        self.log_event(from_='GM', to='Player 1', action=action)

        # make an API call (or get a programmatic response) from player a
        prompt, raw_answer, answer = self.player_a(self.player_a.history,
                                                self.current_turn)
        
        # add reply to its own memory
        #self._append_utterance(answer, 'a', 'assistant')

        # also add reply to the records
        action = {'type': 'get message', 'content': answer}
        self.log_event(from_='Player 1', to='GM', action=action,
                    call=(copy.deepcopy(prompt), raw_answer))

        # increase the number of API requests 
        self.request_counts[self.current_turn] += 1
        return answer    

    def turn(self) -> None:
        """Perform a game turn, utterances by A and B (firstlast specific)."""

        # get player A's reply and add it to its history
        answer_a = self._get_instructions('a')

        # check if the game should be aborted or lost
        is_valid_turn = self._check_validity(answer_a)
        if not is_valid_turn:
            # stop game
            return None

        self.complete_turns += 1    

    def log_eval_assets(self) -> None:
        """Aux to log variables needed for scoring (firstlast specific)"""
        self.log_key('Played turns', self.current_turn)
        self.log_key('Complete turns', self.complete_turns)
        self.log_key(ms.METRIC_ABORTED, self.aborted)
        self.log_key(ms.METRIC_LOSE, self.lose)
        self.log_key(ms.METRIC_REQUEST_COUNT, self.request_counts)
        self.log_key(ms.METRIC_REQUEST_COUNT_PARSED, self.parsed_request_counts)
        self.log_key(ms.METRIC_REQUEST_COUNT_VIOLATED, self.violated_request_counts)
        self.log_key('Evaluation', self.game_result)
        self.log_key('Dialogue', self.dialogue_data)   
        

class DetectObjectGameScorer(GameScorer):
    def __init__(self, game_name: str, experiment: Dict, game_instance: Dict):
        super().__init__(game_name, experiment, game_instance)
        self.dobjeval = ObjDetectEvaluator()



    def compute_scores(self, episode_interactions: Dict) -> None:
        """Compute episode-level and turn-level scores (mandatory)."""

        #if not episode_interactions[ms.METRIC_ABORTED]:
        results = episode_interactions["Evaluation"]
        dialogue_data = episode_interactions["Dialogue"]

        #TODO: Add the logic to evaluate the results
        turn_scores, episode_scores = self.dobjeval.run(results)

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
            '''
            self.log_turn_score(turn, "tp", turn_scores[turn+1]["tp"])
            self.log_turn_score(turn, "fp", turn_scores[turn+1]["fp"])
            self.log_turn_score(turn, "fn", turn_scores[turn+1]["fn"])
            '''
            self.log_turn_score(turn, "nc", turn_scores[turn+1]["nc"])
            self.log_turn_score(turn, "nt", turn_scores[turn+1]["nt"])
            self.log_turn_score(turn, "np", turn_scores[turn+1]["np"])

            self.log_turn_score(turn, "is_cr_turn", turn_scores[turn+1]["is_cr_turn"])
            self.log_turn_score(turn, "individual_property", turn_scores[turn+1]["individual_property"])
            self.log_turn_score(turn, "dialogue_history", turn_scores[turn+1]["dialogue_history"])
            self.log_turn_score(turn, "relational_context", turn_scores[turn+1]["relational_context"])

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

        for key, value in episode_scores.items():
            self.log_episode_score(key, value)



class DetectObjectGameBenchmark(GameBenchmark):
    """Integrate the game into the benchmark run."""
    def __init__(self):
        super().__init__(GAME_NAME)

    # defines whether the game is single player or not
    def is_single_player(self):
        return True

    # add a description of your game
    def get_description(self):
        return "A simple game to detect object id in the given world."

    # copy this, replacing the name of the game master in the return statement
    def create_game_master(self,
                           experiment: Dict,
                           player_backends: List[str]
                           ) -> GameMaster:
        return DetectObject(experiment, player_backends)
    
    def create_game_scorer(self, experiment: Dict, game_instance: Dict) -> GameScorer:
        return DetectObjectGameScorer(self.name, experiment, game_instance)        