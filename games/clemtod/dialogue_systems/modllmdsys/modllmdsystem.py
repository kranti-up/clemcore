from typing import Dict
from games.clemtod.dialogue_systems.basedsystem import DialogueSystem
from games.clemtod.dialogue_systems.modllmdsys.modllmdm import ModLLMDM
from games.clemtod.dialogue_systems.modllmdsys.players import ModLLMSpeaker

class MODULARLLMDialogueSystem(DialogueSystem):
    """A neural network-based dialogue system implementation."""

    def __init__(self, model_name, model_spec, prompts_dict, resp_json_schema, liberal_processing, booking_mandatory_keys, **kwargs):
        super().__init__(**kwargs)

        modllm_player = ModLLMSpeaker(model_spec, "modular_llm", "", {})
        player_dict = {"modllm_player": modllm_player}

        self.modllm = ModLLMDM(model_name, model_spec, prompts_dict, player_dict, resp_json_schema, liberal_processing)

    def process_user_input(self, user_input: str, current_turn: int) -> str:
        return self.modllm.run(user_input, current_turn)
    
    def get_booking_data(self) -> Dict:
        """Returns generated slots."""
        return self.modllm.get_booking_data()
