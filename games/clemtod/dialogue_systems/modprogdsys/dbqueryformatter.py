import copy
from typing import Dict, Any, List, Tuple
import json

import clemgame
from clemgame import get_logger
from games.clemtod.dialogue_systems.modprogdsys.players import ModProgLLMSpeaker
from games.clemtod.utils import cleanupanswer

logger = get_logger(__name__)


class DBQueryFormatter:
    def __init__(self, model_name, model_spec, db_query_prompt, json_format):
        self.model_name = model_name
        self.model_spec = model_spec
        self.base_prompt = db_query_prompt
        self.player = None
        self.base_json_schema = json_format
        self.json_schema_prompt = None
        self._setup()

    def _prepare_response_json_schema(self):
        db_schema = self.base_json_schema["properties"]["details"]["oneOf"][1]
        booking_schema = self.base_json_schema["properties"]["details"]["oneOf"][2]
        self.json_schema_prompt = {
                                "type": "object",
                                "properties": {
                                    "dbquery_format": {
                                        "type": "object",
                                        "description": "A dictionary containing key-value pairs formatted from the input",
                                        "anyOf": [
                                            db_schema,
                                            booking_schema,                                                            
                                        ]
                                    }
                                },
                                "required": ["dbquery_format"]
                            }        


    def _setup(self) -> None:
        # If the model_name is of type "LLM", then we need to instantiate the player
        # TODO: Implement for other model types ("Custom Model", "RASA", etc.)
        self.player = ModProgLLMSpeaker(self.model_spec, "dbquery_formatter", "", {})
        #self.player.history.append({"role": "user", "content": self.base_prompt})
        self._prepare_response_json_schema()

    def run(self, utterance: Dict, turn_idx: int) -> str:
        self.player.history = [{"role": "user", "content": self.base_prompt}]     
        message = json.dumps(utterance) if isinstance(utterance, Dict) else utterance
        self.player.history[-1]["content"] += message

        prompt, raw_answer, answer = self.player(self.player.history, turn_idx, None, self.json_schema_prompt)
        logger.info(f"DBQuery Formatter raw response:\n{answer}")
        return prompt, raw_answer, cleanupanswer(answer)
    
    def get_history(self):
        return self.player.history
    
    def clear_history(self):
        self.player.history = [{"role": "user", "content": self.base_prompt}]    
