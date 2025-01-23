import random
from typing import List
import json

from clemgame.clemgame import Player


class ModularProgSpeaker(Player):
    def __init__(self, model_name: str, player: str, task: str, slots: dict):
        # always initialise the Player class with the model_name argument
        # if the player is a program and you don't want to make API calls to
        # LLMS, use model_name="programmatic"
        super().__init__(model_name)

        self.player: str = player
        self.task = task
        self.slots = slots

        # a list to keep the dialogue history
        self.history: List = []

    # implement this method as you prefer, with these same arguments
    def _custom_response(self, messages, turn_idx) -> str:
        """Return a mock message with the suitable letter and format."""
        slotsdict = dict.fromkeys(self.slots, '')
        if self.player == 'A':
            if turn_idx == 1:
                return self.task
            elif turn_idx == 2:
                return "Yes, please"
            else:
                return "DONE"
        else:
            if self.player == 'intent_detection':
                return '{"intent_detection": "booking-request"}'
            elif self.player == 'slot_extraction':
                return '{"slot_extraction": ' + json.dumps({'area': 'centre'}) + '}'
            elif self.player == 'followup_generation':
                return '{"followup_generation": "Okay, looks good. Do you want to book it?"}'
            elif self.player == 'B':
                raise NotImplementedError("Player B not implemented yet.")


