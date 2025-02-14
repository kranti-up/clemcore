import copy
from typing import Dict, Any, List, Tuple
import json

import clemgame
from clemgame import get_logger
from games.dmsystem_modular_prog.players import ModularProgSpeaker
from games.todsystem.utils import cleanupanswer

logger = get_logger(__name__)


class SlotExtractor:
    def __init__(self, model_name, model_spec, slot_ext_prompt, json_format):
        self.model_name = model_name
        self.model_spec = model_spec
        self.base_prompt = slot_ext_prompt
        self.base_json_schema = json_format
        self.json_schema_prompt = None
        self.player = None
        self._setup()

    def _prepare_response_json_schema(self):
        db_schema = self.base_json_schema["properties"]["details"]["oneOf"][1]
        booking_schema = self.base_json_schema["properties"]["details"]["oneOf"][2]
        self.json_schema_prompt = {
                                        "type": "object",
                                        "properties": {
                                            "slot_extraction": {
                                                "type": "object",
                                                "description": "A dictionary containing key-value pairs extracted from the input text",
                                                "anyOf": [
                                                    db_schema,
                                                    booking_schema,                                           
                                                ]
                                            }
                                        },
                                        "required": ["slot_extraction"]
                                    } 


    def _setup(self) -> None:
        # If the model_name is of type "LLM", then we need to instantiate the player
        # TODO: Implement for other model types ("Custom Model", "RASA", etc.)
        self.player = ModularProgSpeaker(self.model_spec, "slot_extraction", "", {})
        #self.player.history.append({"role": "user", "content": self.base_prompt})
        self._prepare_response_json_schema()

    def run(self, utterance: Dict, turn_idx: int) -> str:
        self.player.history = [{"role": "user", "content": self.base_prompt}]
        message = json.dumps(utterance) if isinstance(utterance, Dict) else utterance
        self.player.history[-1]["content"] += message

        prompt, raw_answer, answer = self.player(self.player.history, turn_idx, None, self.json_schema_prompt)
        logger.info(f"Slot extractor raw response:\n{answer}")
        return prompt, raw_answer, cleanupanswer(answer)
    
    def get_history(self):
        return self.player.history
    
    def clear_history(self):
        self.player.history = [{"role": "user", "content": self.base_prompt}]     
