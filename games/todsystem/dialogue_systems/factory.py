from games.todsystem.dialogue_systems.basedsystem import DialogueSystem
from games.todsystem.dialogue_systems.xuetaldsys.xuetaldsystem import XUETALDialogueSystem
from games.todsystem.dialogue_systems.hetaldsys.hetaldsystem import HETALDialogueSystem
from games.todsystem.dialogue_systems.cetaldsys.cetaldsystem import CETALDialogueSystem

def get_dialogue_system(system_name: str, **kwargs) -> DialogueSystem:
    """Returns an instance of the specified dialogue system."""
    dialogue_systems = {
        "xuetal": XUETALDialogueSystem,
        "hetal": HETALDialogueSystem,
        "cetal": CETALDialogueSystem,
    }

    if system_name in dialogue_systems:
        return dialogue_systems[system_name](**kwargs)
    else:
        raise ValueError(f"Unknown dialogue system: {system_name}")
