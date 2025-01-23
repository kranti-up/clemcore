import copy
from typing import Dict, Any, List, Tuple
import json

import clemgame
from clemgame import get_logger
from games.dmsystem_modular_prog.players import ModularProgSpeaker
from games.dmsystem_monolithic_llm.utils import cleanupanswer

logger = get_logger(__name__)


class SlotExtractor:
    def __init__(self, model_name: str, slot_ext_prompt: List[Dict]):
        self.model_name = model_name
        self.base_prompt = slot_ext_prompt
        self.player = None
        self._setup()

    def _setup(self) -> None:
        # If the model_name is of type "LLM", then we need to instantiate the player
        # TODO: Implement for other model types ("Custom Model", "RASA", etc.)
        self.player = ModularProgSpeaker(self.model_name, "slot_extraction", "", {})
        #self.player.history.append({"role": "user", "content": self.base_prompt})

    def run(self, utterance: Dict, turn_idx: int) -> str:
        self.player.history = [{"role": "user", "content": self.base_prompt}]
        message = json.dumps(utterance) if isinstance(utterance, Dict) else utterance

        self.player.history[-1]["content"] += message

        prompt, raw_answer, answer = self.player(self.player.history, turn_idx, None)
        logger.info(f"Slot extractor raw response:\n{answer}")
        return cleanupanswer(answer)
    
    def get_history(self):
        return self.player.history
    
    def clear_history(self):
        self.player.history = [{"role": "user", "content": self.base_prompt}]     
