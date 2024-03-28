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

    elif variant == "single_turn":
        result = "\n".join(
            f"{instruction_label}\n{ic_sample[0]}\n\n{output_label_horder}\n{ic_sample[1]['function']}\n\n{output_label_horder_usage}\n{ic_sample[1]['usage']}\n"
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
    SEED

):
    print(f"board: {board}, board_object: {board_object}, variant: {variant}, combo_name: {test_combo_name}")
    if board not in ["sb", "rb"] or board_object not in ["so", "ro"] or variant not in ["single_turn", "multi_turn", "regular"]:
        raise ValueError(f"Invalid board: {board} or board_object: {board_object} or variant:{variant}")

    board_type = "simple" if board == "sb" else "regular"
    board_object_type = "simple" if board_object == "so" else "complex"

    train_shapes = train_samples[board_type][board_object_type]

    filtered_samples = {k: v for k, v in train_shapes[total_shapes].items() if k != test_combo_name}

    incontext_samples = []
    for combo in filtered_samples:
        sample = random.choice(filtered_samples[combo])
        #for sample in filtered_samples[combo]:
        dialog = sample["dialogues"][variant]["instructions"]

        for d_ in dialog:
            if variant == "multi_turn":
                incontext_samples.append((d_["<Programmer>"], d_["<Editor>"]))
            elif variant == "single_turn":
                incontext_samples.append((d_["<Programmer>"], {"function":d_["<Editor>"]["function"], "usage": d_["<Editor>"]["usage"]}))
            elif variant == "regular":
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
