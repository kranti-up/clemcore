from games.todsystem.dialogue_systems.basedsystem import DialogueSystem
from games.todsystem.dialogue_systems.xuetaldsys.xuetaldsystem import XUETALDialogueSystem
from games.todsystem.dialogue_systems.hetaldsys.hetaldsystem import HETALDialogueSystem
from games.todsystem.dialogue_systems.cetaldsys.cetaldsystem import CETALDialogueSystem
from games.todsystem.dialogue_systems.monolithicsys.monodsystem import MONODialogueSystem
from games.todsystem.dialogue_systems.modprogdsys.modprogdsystem import MODULARPROGDialogueSystem
from games.todsystem.dialogue_systems.modllmdsys.modllmdsystem import MODULARLLMDialogueSystem

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
