import copy
from typing import Dict, Any, List, Tuple
import json

import clemgame
from clemgame import get_logger
from games.todsystem.dialogue_systems.modprogdsys.players import ModProgLLMSpeaker
from games.todsystem.utils import cleanupanswer

logger = get_logger(__name__)


class IntentDetector:
    def __init__(self, model_name, model_spec, intent_det_prompt):
        self.model_name = model_name
        self.model_spec = model_spec
        self.base_prompt = intent_det_prompt
        self.player = None
        self.json_schema = None
        self._setup()

    def _prepare_response_json_schema(self):
        self.json_schema_prep = {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "enum": ["restaurant", "hotel", "attraction", "train", "taxi", "donotcare"]
                        },
                        "intent_detection": {
                            "type": "string",
                            "enum": ["booking-request", "booking-success", "booking-failure",
                                     "dbretrieval-request", "dbretrieval-success", "dbretrieval-failure",
                                     "detection-unknown"]
                        }
                    },
                    "required": ["domain", "intent_detection"]
                }

    def _setup(self) -> None:
        # If the model_name is of type "LLM", then we need to instantiate the player
        # TODO: Implement for other model types ("Custom Model", "RASA", etc.)
        self.player = ModProgLLMSpeaker(self.model_spec, "intent_detection", "", {})
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
        prompt, raw_answer, answer = self.player(self.player.history, turn_idx, None, self.json_schema)
        logger.info(f"Intent detection raw response:\n{answer}")
        answer =  cleanupanswer(answer)
        #self.player.history.append({"role": "assistant", "content": json.dumps(answer)})

        return prompt, raw_answer, answer
    
    def get_history(self):
        return self.player.history
    
    def clear_history(self):
        self.player.history = [{"role": "user", "content": self.base_prompt}]
