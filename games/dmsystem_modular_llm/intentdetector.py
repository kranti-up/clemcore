import copy
from typing import Dict, Any, List, Tuple
import json

import clemgame
from clemgame import get_logger
from games.dmsystem_modular_llm.players import ModularLLMSpeaker
from games.dmsystem_monolithic_llm.utils import cleanupanswer

logger = get_logger(__name__)


class IntentDetector:
    def __init__(self, model_name: str, intent_det_prompt: List[Dict]):
        self.model_name = model_name
        self.base_prompt = intent_det_prompt
        self.player = None
        self._setup()

    def _setup(self) -> None:
        # If the model_name is of type "LLM", then we need to instantiate the player
        # TODO: Implement for other model types ("Custom Model", "RASA", etc.)
        self.player = ModularLLMSpeaker(self.model_name, "intent_detection", "", {})
        self.player.history.append({"role": "user", "content": self.base_prompt})

    def run(self, utterance: Dict, turn_idx: int) -> str:
        message = json.dumps(utterance) if isinstance(utterance, Dict) else utterance

        self.player.history[-1]["content"] += message

        prompt, raw_answer, answer = self.player(self.player.history, turn_idx, None)
        logger.info(f"Intent detection raw response:\n{answer}")
        return cleanupanswer(answer)
    
    def get_history(self):
        return self.player.history
    
    def clear_history(self):
        self.player.history = [{"role": "user", "content": self.base_prompt}]
