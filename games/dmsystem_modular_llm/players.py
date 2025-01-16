import random
from typing import List
import json

from clemgame.clemgame import Player


class ModularLLMSpeaker(Player):
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
                return '{"intent": "inform"}'
            elif self.player == 'slot_extraction':
                return '{"slots": ' + json.dumps({'date': '2022-12-25'}) + '}'
            elif self.player == 'followup_generation':
                return '{"followup_generation": "Okay, looks good. Do you want to book it?"}'
            elif self.player == 'booking_aggregator':
                return '{"slots": ' + json.dumps({'date': '2022-12-25'}) + '}'
                
            elif self.player == 'B':
                subsystems = [
                    ("intent_detector", '{"user_request": "I want to book a room in centre"}'),
                    ("slot_extractor", '{"user_request": "I want to book a room in centre"}'),
                    ("db_retriever", '{"area": "centre"}'),
                    ("followup_generator", '{"area": "centre"}'),
                    ("booking_aggregator", '{"area": "centre"}'),
                    ("booking_confirmer", '{"area": "centre"}')
                ]

                if self.cursystem is None:
                    self.cursystem = subsystems[0][0]
                    return f'{{"next_subsystem": "{self.cursystem}", "input_data": {subsystems[0][1]}}}'

                for i, (system, data) in enumerate(subsystems):
                    if self.cursystem == system:
                        next_system = subsystems[i + 1][0] if i + 1 < len(subsystems) else None
                        self.cursystem = next_system
                        if next_system:
                            return f'{{"next_subsystem": "{next_system}", "input_data": {data}}}'
                        else:
                            return f'{{"status": "booking-confirmed", "details": {data}}}'

                if self.cursystem == "followup_generator":
                    self.cursystem = "booking_aggregator"
                    return '{"status": "follow-up", "details": "do you want to proceed with the booking?"}'

