import random
from string import ascii_lowercase as letters
from typing import List

from clemgame.clemgame import Player


class InstructionGiver(Player):
    def __init__(self, model_name: str, player: str):
        # always initialise the Player class with the model_name argument
        # if the player is a program and you don't want to make API calls to
        # LLMS, use model_name="programmatic"
        super().__init__(model_name)
        self.player: str = player

        # a list to keep the dialogue history
        self.history: List = []

    # implement this method as you prefer, with these same arguments
    def _custom_response(self, messages, turn_idx) -> str:
        """Return a mock message with the suitable output format."""
        inst_type = "atomic"
        user_content = messages[-1]
        if user_content["role"] == "user":
            instruction = user_content["content"].split("\n")[-2]
            if "This is" in instruction:
                inst_type = "compound"

        if self.player == 'A':
            if inst_type == "atomic":
                return "Output\nput(board, shape='screw', color='yellow', x=1, y=5)"
            else:
                data = "Function:\ndef place_shape(board, colors, x, y):\n\tput(board, 'screw', colors[0], x, y \n\nUsage:\nplace_shape(board, ['yellow'], 1, 5)"
            return data