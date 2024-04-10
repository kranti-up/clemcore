import random

def format_incontext_samples(
    board,
    board_object,
    variant,
    incontext_samples,
    incontext_labels,
):
    instruction_label = incontext_labels["INSTRUCTION_LABEL"]
    output_label_forder = incontext_labels["OUTPUT_LABEL"]
    output_label_horder = incontext_labels["OUTPUT_LABEL_HORDER"]
    output_label_horder_usage = incontext_labels["OUTPUT_LABEL_HORDER_USAGE"]

    if variant == "multi_turn":
        result = "\n".join(
            f"{instruction_label}\n{ic_sample[0]}\n\n{output_label_forder}\n{ic_sample[1]}\n"
            for ic_sample in incontext_samples
        )

        return result

    elif variant in ["single_turn", "single_turn_sc", "single_turn_hai", "single_turn_hai_sc", "single_turn_mg"]:
        result = "\n".join(
            f"{instruction_label}\n{ic_sample[0]}\n\n{output_label_horder}\n{ic_sample[1]['function']}\n\n{output_label_horder_usage}\n{ic_sample[1]['usage']}\n"
            for ic_sample in incontext_samples
        )
        return result
    
    elif variant in ["regular", "regular_hai", "regular_mg"]:
        result = "\n".join(
            f"{instruction_label}\n{ic_sample[0]}\n\n{output_label_forder}\n{ic_sample[1]}\n"
            for ic_sample in incontext_samples
        )
        return result


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
    SEED

):
    print(f"board: {board}, board_object: {board_object}, variant: {variant}, combo_name: {test_combo_name}")
    if board not in ["sb", "rb"] or board_object not in ["so", "ro", "cho"] or variant not in ["single_turn", "single_turn_sc", "multi_turn", "regular", "single_turn_hai", "single_turn_hai_sc", "regular_hai", "single_turn_mg", "regular_mg"]:
        raise ValueError(f"Invalid board: {board} or board_object: {board_object} or variant:{variant}")

    board_type = "simple" if board == "sb" else "regular"
    if board_object == "so":
        board_object_type = "simple"
    elif board_object == "cho":
        board_object_type = "challenge"    
    else:
        board_object_type = "complex"

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


    incontext_samples = []
    if variant in ["single_turn_hai", "single_turn_mg"]:
        use_train_dlg_variant = "single_turn"
    elif variant == "single_turn_hai_sc":
        use_train_dlg_variant = "single_turn_sc"
    elif variant in ["regular_hai", "regular_mg"]:
        use_train_dlg_variant = "regular"
    else:
        use_train_dlg_variant = variant

    for combo in filtered_samples:
        #samples_count = 3
        #if len(filtered_samples[combo]) < samples_count:
        #    samples_count = len(filtered_samples[combo])
        #sel_samples = random.sample(filtered_samples[combo], k=samples_count)
        for sample in filtered_samples[combo]:
            dialog = sample["dialogues"][use_train_dlg_variant]["instructions"]

            for d_ in dialog:
                if variant == "multi_turn":
                    incontext_samples.append((d_["<Programmer>"], d_["<Editor>"]))
                elif variant in ["single_turn", "single_turn_sc", "single_turn_hai", "single_turn_hai_sc", "single_turn_mg"]:
                    incontext_samples.append((d_["<Programmer>"], {"function":d_["<Editor>"]["function"], "usage": d_["<Editor>"]["usage"]}))
                elif variant in ["regular", "regular_hai", "regular_mg"]:
                    incontext_samples.append((d_["<Programmer>"], d_["<Editor>"]["output"]))
            #break

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
        )

    return incontext_samples
