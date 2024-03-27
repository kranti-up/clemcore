import re
from collections import Counter

import numpy as np
import json

from copy import deepcopy

from games.ccbts.utils.coco import (
    init_board,
    put,
    SameShapeStackingError,
    SameShapeAtAlternateLevels,
    NotOnTopOfScrewError,
    DepthMismatchError,
)

def _check_gen_code_format(self, generated_code):
    # pattern = r"put\(board, shape='.+', color='.+', x=\d+, y=\d+\)"
    pattern = r"^put\(board, shape='.+', color='.+', x=\d+, y=\d+\)$"
    # print("Matching Pattern  -> ",generated_code)
    if re.match(pattern, generated_code):
        return True
    else:
        pattern = r"^put\(board, '.+', '.+', \d+, \d+\)$"
        if re.match(pattern, generated_code):
            return True
        else:
            pattern = r"^put\(board, \".+\", \".+\", \d+, \d+\)$"
            if re.match(pattern, generated_code):
                return True
        return False

def _execute_instructions(instruction, board):
    try:
        if instruction[-1] in ["\n", ";", ".", ","]:
            instruction = instruction[:-1]

        #if self._check_gen_code_format(instruction):
        exec(instruction)
        return board.copy(), None
    except Exception as e:
        return None, type(e).__name__

def _list_occupied_cells_with_details(board):
    occupied_cells = {}

    if board is None:
        return occupied_cells

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
                occupied_cells[f"{row}:{col}"] = cell_elements

    return occupied_cells

def update_overall_results(episode_path, gt_board, gen_board, status):
    if not episode_path:
        return

    gt_occupied_cells = _list_occupied_cells_with_details(gt_board)
    gen_occupied_cells = _list_occupied_cells_with_details(gen_board)

    #print("GT Board Occupied Cells: ",gt_occupied_cells)
    #print("GEN Board Occupied Cells: ",gen_occupied_cells)
    #input()

    path_details = episode_path.split("/")
    model_name = path_details[0]
    exp_name = path_details[1]
    episode_id = path_details[2]

    result = {"episode_path": episode_path, "gt_occupied_cells": gt_occupied_cells, "gen_occupied_cells": gen_occupied_cells,
              "status": status}

    try:
        with open("overall_analysis.json", "r") as f:
            data = json.load(f)
            #print("Loaded data", data)
            #input()
    except FileNotFoundError:
        data = {}
        #print("File not found")

    print(data)
    #input()

    if model_name in data:
        if exp_name in data[model_name]:
            data[model_name][exp_name][episode_id] = result
            print("Added episode")
            #input()
        else:
            data[model_name][exp_name] = {episode_id: result}
            print("added experiment")
            #input()
    else:
        data[model_name] = {exp_name: {episode_id: result}}
        print("added model")
        #input()

    #print(data)
    #input()

    with open("overall_analysis.json", "w") as f:
        json.dump(data, f, indent=4)

    #print("Saved to file")
    #input()        
        
def _element_mismatch(gt_board, gen_board):
    gt_occupied_cells = _list_occupied_cells_with_details(gt_board)
    gen_occupied_cells = _list_occupied_cells_with_details(gen_board)

    print("GT Board Occupied Cells: ",gt_occupied_cells)
    print("GEN Board Occupied Cells: ",gen_occupied_cells)
    
    gt_locations = set(gt_occupied_cells.keys())
    gen_locations = set(gen_occupied_cells.keys())

    for loc in gt_locations:
        if loc in gen_locations:
            if len(gt_occupied_cells[loc]) != len(gen_occupied_cells[loc]):
                return "mismatch_count"
            shapes_gt = [shape for shape, _ in gt_occupied_cells[loc]]
            shapes_gen = [shape for shape, _ in gen_occupied_cells[loc]]

            if set(shapes_gt) == set(shapes_gen):
                if shapes_gt != shapes_gen:# and set(colors_gt) == set(colors_gen) and colors_gt != colors_gen:
                    return "mismatch_order"
            else:
                return "mismatch_shape"


            for index in range(len(gt_occupied_cells[loc])):
                _, shape_color_gt = gt_occupied_cells[loc][index]
                _, shape_color_gen = gen_occupied_cells[loc][index]
                if shape_color_gt != shape_color_gen:
                    return "mismatch_color"
        else:
            return "mismatch_location"



    if len(gt_locations) != len(gen_locations):
        missing_locations = gt_locations - gen_locations
        return f"Missing Locations: {missing_locations}"

    print(f"GT Locations: {gt_occupied_cells}, Gen Locations: {gen_occupied_cells}")
    input()
    #return gt_occupied_cells, gen_occupied_cells
    return "some mismatch!"

def handlerepeat(ground_truth, prediction):
    if "output" in ground_truth and ground_truth["output"] and "function" in ground_truth and ground_truth["function"]:
        gt_mod = deepcopy(ground_truth)
        pred_mod = deepcopy(prediction)

        gt_mod["output"] = gt_mod["function"] + "\n" + gt_mod["output"]
        pred_mod["output"] = gt_mod["function"] + "\n" + pred_mod["output"]

        gt_mod["function"] = None

        return gt_mod, pred_mod

    else:
        return ground_truth, prediction


def exec_comparison(rows, cols, ground_truth, prediction, results):

    def compare_boards(gt_code, gen_code):
        #episode_path = f"/home/admin/Desktop/codebase/cocobots/llm_gm/clembench/{episode_path}/"
        #os.makedirs(os.path.dirname(episode_path), exist_ok=True)
      
        gt_board = init_board(rows, cols)
        gt_board, gt_exec = _execute_instructions(gt_code, gt_board)

        gen_board = init_board(rows, cols)
        if gen_code and "while" in gen_code:
            gen_exec = "While loop not supported"
        else:
            gen_board, gen_exec = _execute_instructions(gen_code, gen_board)

        if gt_board is None or gen_board is None or gt_exec or gen_exec:
            #plot_board(gt_board, f"{episode_path}gt_board_placement_error.png")
            #plot_board(gen_board, "gen_ele_mismatch.png")
            #update_overall_results(episode_path, gt_board, gen_board, "board_placement_error")
            return "board_placement_error", gen_exec
        else:
            #print("GT Board Occupied Cells: ",_list_occupied_cells_with_details(gt_board))
            #print("GEN Board Occupied Cells: ",_list_occupied_cells_with_details(gen_board))
            if not np.array_equal(gt_board, gen_board):
                #plot_board(gt_board, f"{episode_path}gt_ele_mismatch.png")
                #plot_board(gen_board, f"{episode_path}gen_ele_mismatch.png")
                #update_overall_results(episode_path, gt_board, gen_board, "element_mismatch")
                elemt_error = _element_mismatch(gt_board, gen_board)
                return "element_mismatch", elemt_error


        #plot_board(gt_board, f"{episode_path}gt_success.png")
        #plot_board(gen_board, f"{episode_path}gen_success.png")
        #update_overall_results(episode_path, gt_board, gen_board, "no error")
        return "no error", None


    def evaluate_item(gt_item, gen_item):
        exec_result = {}
        for key in gt_item:
            if not gt_item[key] or key not in gen_item or not gen_item[key] or key == "usage":
                continue

            fail_reason, detail_error  = compare_boards(gt_item[key], gen_item[key])
            status = "success" if fail_reason == "no error" else "failure"
            #exec_result[key] = {"status": status, "fail_reason": fail_reason, "detail_error": detail_error}
            exec_result = {"status": status, "fail_reason": fail_reason, "detail_error": detail_error}
        return exec_result


    print("Ground Truth: ", ground_truth)
    print("Prediction: ", prediction)

    ground_truth, prediction = handlerepeat(ground_truth, prediction)

    exec_result = evaluate_item(ground_truth, prediction)

    #exec_match_type = "success" if all(result["status"] == "success" for result in exec_result.values()) else "failure"
    exec_match_type = exec_result["status"]
    results[exec_match_type] += 1

    return exec_match_type, exec_result 


if __name__=="__main__":
    rows = 8
    cols = 8

    ground_truth = {
        #'output': "put(board, shape='bridge-h', color='blue', x=5, y=3)",
        #'function': None, 'usage': None
       'output': "Function\ndef bhs2(board, shapes, colors, x, y):\n\tput(board, shapes[0], colors[0], x, y)\n\tput(board, shapes[1], colors[1], x, y)\n\tput(board, shapes[2], colors[2], x, y+1)\n\nUsage\nbhs2(board, ['bridge-h', 'screw', 'screw'], ['yellow', 'green', 'green'], 5,4)",
        'function': "def bhs2(board, shapes, colors, x, y):\n\tput(board, shapes[0], colors[0], x, y)\n\tput(board, shapes[1], colors[1], x, y)\n\tput(board, shapes[2], colors[2], x, y+1)\nbhs2(board, ['bridge-h', 'screw', 'screw'], ['yellow', 'green', 'green'], 5,4)",
        'usage': "bhs2(board, ['bridge-h', 'screw', 'screw'], ['yellow', 'green', 'green'], 5,4)"     
    }

    prediction = {
        #'output': "put(board, shape='bridge-h', color='blue', x=5, y=3)",
        #'function': None, 'usage': None
        'function': "def bhs2(board, shape, colors, x, y):\n    put(board, shape, colors[0], x, y)\n    put(board, 'washer', colors[1], x, y)\n    put(board, 'washer', colors[1], x, y+1)\n\n\n\n\nbhs2(board, 'bridge-h', ['yellow', 'green'], 5, 4)",
         'usage': "bhs2(board, 'bridge-h', ['yellow', 'green'], 5, 4)"     
    }

    results = {
                    "exact_match": Counter(),
                    "codebleu": Counter(),
                    "exec_score": Counter(),
                  }

    print(exec_comparison(rows, cols, ground_truth, prediction, results["exec_score"]))