import random

def format_incontext_samples(
    board,
    board_object,
    variant,
    incontext_samples,
    incontext_labels,
    player_name,
):
    instruction_label = incontext_labels["INSTRUCTION_LABEL"]
    output_label_forder = incontext_labels["OUTPUT_LABEL"]
    output_label_horder = incontext_labels["OUTPUT_LABEL_HORDER"]
    output_label_horder_usage = incontext_labels["OUTPUT_LABEL_HORDER_USAGE"]
    grid_explanation = incontext_labels["GRID_EXPLANATION"]


    if variant == "multi_turn":
        result = "\n".join(
            f"{instruction_label}\n{ic_sample[0]}\n\n{output_label_forder}\n{ic_sample[1]}\n"
            for ic_sample in incontext_samples
        )

        return result

    elif variant in ["single_turn", "single_turn_sc"] or (player_name == "player_b" and variant in ["single_turn_ge", "single_turn_gi", "single_turn_gei"]):
        result = "\n".join(
            f"{instruction_label}\n{ic_sample[0]}\n\n{output_label_horder}\n{ic_sample[1]['function']}\n\n{output_label_horder_usage}\n{ic_sample[1]['usage']}\n"
            for ic_sample in incontext_samples
        )
        return result
    
    elif variant == "regular":
        result = "\n".join(
            f"{instruction_label}\n{ic_sample[0]}\n\n{output_label_forder}\n{ic_sample[1]}\n"
            for ic_sample in incontext_samples
        )
        return result
    
    elif variant == "single_turn_ge":
        result = "\n".join(
            f"'{ic_sample[0]}'\n{ic_sample[1]}\n\n{grid_explanation}\n{ic_sample[2]}\n"
            for ic_sample in incontext_samples
        )
        return result
    
    elif variant == "single_turn_gi":
        result = "\n".join(
            f"'{ic_sample[0]}'\n{ic_sample[1]}\n\n{instruction_label}\n{ic_sample[2]}\n"
            for ic_sample in incontext_samples
        )
        return result    
    
    elif variant == "single_turn_gei":
        result = "\n".join(
            f"'{ic_sample[0]}'\n{ic_sample[1]}\n\n{grid_explanation}\n{ic_sample[2]}\n{instruction_label}\n{ic_sample[3]}\n"
            for ic_sample in incontext_samples
        )
        return result      
    

def get_board_ascii_details(board):
    empty_cell = "⬜️"
    board_details = [[empty_cell for _ in range(board["rows"])] for _ in range(board["cols"])]

    for index, shape in enumerate(board["shapes"]):
        x, y = board["x"][index], board["y"][index]
        color = board["colors"][index]

        if board_details[x][y] == empty_cell:
            board_details[x][y] = [(shape, color)]
        else:
            board_details[x][y].append((shape, color))  

    #print(board_details)
    #input()

    return board_details    

def get_board_explanation(board, combo_name):
    board_details = get_board_ascii_details(board)
    shape_names = {"washer": "washer", "nut": "nut", "screw": "screw", "bridge-v": "vertical bridge", "bridge-h": "horizontal bridge"}
    explanation = []
    for i in range(len(board_details)):
        for j in range(len(board_details[i])):
            if board_details[i][j] != "⬜️":
                cell_info = f"Row({i+1}), Col({j+1}) contains"
                for shape, color in board_details[i][j]:
                    cell_info += f" {color} {shape_names[shape]},"
                cell_info = cell_info[:-1]
                explanation.append(cell_info+"."+ "\n")
    explanation = "\n".join(explanation)
    explanation = f"Name of the combination '{combo_name}'. {explanation}"
    return explanation, board_details


def get_incontext_samples(
    board,
    board_object,
    variant,
    num_samples,
    total_shapes,
    test_combo_name,
    train_samples,
    incontext_labels,
    seed_template_name,
    player_name,
    SEED

):
    print(f"board: {board}, board_object: {board_object}, variant: {variant}, combo_name: {test_combo_name}")
    if board not in ["sb", "rb"] or board_object not in ["so", "ro"] or variant not in ["single_turn", "single_turn_sc", "multi_turn", "regular", "single_turn_gei", "single_turn_ge", "single_turn_gi"]:
        raise ValueError(f"Invalid board: {board} or board_object: {board_object} or variant:{variant}")

    board_type = "simple" if board == "sb" else "regular"
    board_object_type = "simple" if board_object == "so" else "complex"

    train_shapes = train_samples[board_type][board_object_type]

    if board_type == "simple":
        filtered_samples = {k: v for k, v in train_shapes[total_shapes].items() if k != test_combo_name}
    else:
        filtered_samples = {}
        for k, v in train_shapes[total_shapes].items():
            if k != test_combo_name:
                for avail_sample in v:
                    if avail_sample["seed_template"] == seed_template_name:
                        continue
                    else:
                        if k not in filtered_samples:
                            filtered_samples[k] = []

                        filtered_samples[k].append(avail_sample)

    if variant in ["single_turn_gei", "single_turn_ge", "single_turn_gi"]:
        use_variant_for_dialogue = "single_turn"  
    incontext_samples = []
    for combo in filtered_samples:
        #samples_count = 3
        #if len(filtered_samples[combo]) < samples_count:
        #    samples_count = len(filtered_samples[combo])
        #sel_samples = random.sample(filtered_samples[combo], k=samples_count)
        if player_name == "player_b":
            for sample in filtered_samples[combo]:              
                dialog = sample["dialogues"][use_variant_for_dialogue]["instructions"]

                for d_ in dialog:
                    if variant == "multi_turn":
                        incontext_samples.append((d_["<Programmer>"], d_["<Editor>"]))
                    elif variant in ["single_turn", "single_turn_sc", "single_turn_gei", "single_turn_ge", "single_turn_gi"]:
                        incontext_samples.append((d_["<Programmer>"], {"function":d_["<Editor>"]["function"], "usage": d_["<Editor>"]["usage"]}))
                    elif variant == "regular":
                        incontext_samples.append((d_["<Programmer>"], d_["<Editor>"]["output"]))
                #break
        else:
            for sample in filtered_samples[combo]:
                dialog = sample["dialogues"][use_variant_for_dialogue]["instructions"]

                for d_ in dialog:
                    board_explanation, board_details = get_board_explanation(sample, sample["combo_name"])
                    if variant == "single_turn_gei":
                        incontext_samples.append((sample["combo_name"], board_details, board_explanation, d_["<Programmer>"]))
                    elif variant == "single_turn_ge":
                        incontext_samples.append((sample["combo_name"], board_details, board_explanation))
                    elif variant == "single_turn_gi":
                        incontext_samples.append((sample["combo_name"], board_details, d_["<Programmer>"]))        


    random.seed(SEED)

    print(f"num_samples: {num_samples}, len(incontext_samples): {len(incontext_samples)}")

    if num_samples:
        incontext_samples = random.sample(incontext_samples, num_samples)
    else:
        incontext_samples = []

    if incontext_samples:
        incontext_samples = format_incontext_samples(
            board,
            board_object,
            variant,
            incontext_samples,
            incontext_labels,
            player_name
        )

    return incontext_samples
