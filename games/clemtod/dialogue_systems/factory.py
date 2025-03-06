from games.clemtod.dialogue_systems.basedsystem import DialogueSystem
from games.clemtod.dialogue_systems.xuetaldsys.xuetaldsystem import XUETALDialogueSystem
from games.clemtod.dialogue_systems.hetaldsys.hetaldsystem import HETALDialogueSystem
from games.clemtod.dialogue_systems.cetaldsys.cetaldsystem import CETALDialogueSystem
from games.clemtod.dialogue_systems.monolithicsys.monodsystem import MONODialogueSystem
from games.clemtod.dialogue_systems.modprogdsys.modprogdsystem import MODULARPROGDialogueSystem
from games.clemtod.dialogue_systems.modllmdsys.modllmdsystem import MODULARLLMDialogueSystem

def get_dialogue_system(system_name: str, **kwargs) -> DialogueSystem:
    """Returns an instance of the specified dialogue system."""
    dialogue_systems = {
        "xuetal": XUETALDialogueSystem,
        "hetal": HETALDialogueSystem,
        "cetal": CETALDialogueSystem,
        "monolithic_llm": MONODialogueSystem,
        "modular_prog": MODULARPROGDialogueSystem,
        "modular_llm": MODULARLLMDialogueSystem
    }

    if system_name in dialogue_systems:
        return dialogue_systems[system_name](**kwargs)
    else:
        raise ValueError(f"Unknown dialogue system: {system_name}")
