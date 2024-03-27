
import re
from collections import Counter

import numpy as np
import json

from games.ccbts_human.utils.coco import (
    init_board,
    put,
    plot_board,
    SameShapeStackingError,
    SameShapeAtAlternateLevels,
    NotOnTopOfScrewError,
    DepthMismatchError,
)


def list_occupied_cells_with_details(board):
    occupied_cells = {}

    for row in range(board.shape[2]):
        for col in range(board.shape[3]):
            cell_elements = []
            # check each layer for the current cell
            for layer in range(board.shape[0]):
                # get shape and color
                shape = board[layer, 0, row, col]
                color = board[layer, 1, row, col]
                # If the shape is not '0', then the cell is occupied
                if shape != "0":
                    cell_elements.append((shape, color))

            if cell_elements:
                occupied_cells[(row, col)] = cell_elements

    return occupied_cells

def cleanup_response(value):
    if "```python" in value:
        value = value.replace("```python", "").strip()
    if "```" in value:
        value = value.replace("```", "").strip()
    if value[0] == ":":
        value = value[1:]
    if value[-1] in ["\n", ";", ".", ","]:
        value = value[:-1]

    return value



def execute_response(rows, cols, game_data, dialogue_pair):
    board = init_board(rows, cols)

    response = game_data["action"]["prediction"]
    if not response:
        return None, "No response available for execution"

    print(response)

    error = False
    for turn, code in response.items():
        print(f"Turn {turn} -> {code}")
        for label, value in code.items():
            print(value)
            value = cleanup_response(value)
            print(f"Cleaned up response = {value}")
            try:
                exec(value)
                print(list_occupied_cells_with_details(board))
                #plot_board(board, f"gen_response_{dialogue_pair}_{turn}.png")
            except Exception as e:
                error = True
                print(list_occupied_cells_with_details(board))
                print(type(e).__name__, e)
                #plot_board(board, f"gen_response_{dialogue_pair}_{turn}.png")
                break
        if error:
            break

    plot_board(board, f"gen_response_{dialogue_pair}.png")


if __name__ == "__main__":
    response = {'1': {'output': "put(board, shape='washer', color='red', x=2, y=3)"}, '2': {'output': "put(board, shape='bridge-h', color='green', x=2, y=2)."}, '3': {'output': "put(board, shape='bridge-v', color='blue', x=5, y=2)."}}
    rows, cols = 8, 8
    game_data = {"action": {"prediction": response}}
    dialogue_pair = "sample_test"
    execute_response(rows, cols, game_data, dialogue_pair)

