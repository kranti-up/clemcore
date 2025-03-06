import copy
from typing import Dict, Any, List, Tuple
import json

import clemgame
from clemgame import get_logger
from games.clemtod.dialogue_systems.modprogdsys.players import ModProgLLMSpeaker
from games.clemtod.utils import cleanupanswer

logger = get_logger(__name__)


class FollowupGenerator:
    def __init__(self, model_name, model_spec, response_gen_prompt):
        self.model_name = model_name
        self.model_spec = model_spec
        self.base_prompt = response_gen_prompt
        self.player = None
        self.json_schema_prompt = None
        self._setup()

    def _prepare_response_json_schema(self):
        self.json_schema_prompt = {
                            "type": "object",
                            "properties": {
                                "followup_generation": {
                                    "type": "string",
                                    "description": "A follow up response based on the input"
                                }
                            },
                            "required": ["followup_generation"]
                            }
    def _setup(self) -> None:
        # If the model_name is of type "LLM", then we need to instantiate the player
        # TODO: Implement for other model types ("Custom Model", "RASA", etc.)
        self.player = ModProgLLMSpeaker(self.model_spec, "followup_generation", "", {})
        #self.player.history.append({"role": "user", "content": self.base_prompt})
        self._prepare_response_json_schema()

    def run(self, utterance: Dict, turn_idx: int) -> str:
        self.player.history = [{"role": "user", "content": self.base_prompt}] 
        message = json.dumps(utterance) if isinstance(utterance, Dict) else utterance
        self.player.history[-1]["content"] += message

        '''
        if self.player.history[-1]["role"] == "user":
            self.player.history[-1]["content"] += message
        else:
            self.player.history.append({"role": "user", "content": message})
        '''
        prompt, raw_answer, answer = self.player(self.player.history, turn_idx, None, None)
        logger.info(f"Follow-up generator raw response:\n{answer}")
        answer =  cleanupanswer(answer)
        #self.player.history.append({"role": "assistant", "content": json.dumps(answer)})

        return prompt, raw_answer, answer

    def get_history(self):
        return self.player.history
    
    def clear_history(self):
        self.player.history = [{"role": "user", "content": self.base_prompt}] 