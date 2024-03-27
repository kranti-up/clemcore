import random

def format_incontext_samples(
    level,
    variant,
    incontext_samples,
    incontext_labels,
):
    instruction_label = incontext_labels["INSTRUCTION_LABEL"]
    output_label_forder = incontext_labels["OUTPUT_LABEL"]
    output_label_horder = incontext_labels["OUTPUT_LABEL_HORDER"]
    output_label_horder_usage = incontext_labels["OUTPUT_LABEL_HORDER_USAGE"]

    if level == "level-1":
        result = "\n".join(
            f"{instruction_label}\n{ic_sample[0]}\n\n{output_label_forder}\n{ic_sample[1]}\n"
            for ic_sample in incontext_samples
        )

        return result

    elif level == "level-2":
        if variant == "forder":
            result_im = []
            for ic_sample in incontext_samples:
                for data in ic_sample:
                    result_im.append(
                        f"{instruction_label}\n{data[0]}\n\n{output_label_forder}\n{data[1]}\n"
                    )
            result = "\n".join(result_im)

            return result

        elif variant == "horder":
            result = "\n".join(
                f"{instruction_label}\n{ic_sample[0]}\n\n{output_label_horder}\n{ic_sample[1]['function']}\n\n{output_label_horder_usage}\n{ic_sample[1]['usage']}\n"
                for ic_sample in incontext_samples
            )
            return result

        elif variant == "horder_step":
            result_im = []
            for ic_sample in incontext_samples:
                for data in ic_sample[:-1]:
                    result_im.append(
                        f"{instruction_label}\n{data[0]}\n\n{output_label_forder}\n{data[1]}\n"
                    )

                result_im.append(
                    f"{instruction_label}\n{ic_sample[-1][0]}\n\n{output_label_horder}\n{ic_sample[-1][1]['function']}\n\n{output_label_horder_usage}\n{ic_sample[-1][1]['usage']}\n"
                )
                # result = "\n".join(result_im)
            result = "\n".join(result_im)

            return result

        elif variant == "horder_adapt":
            result = "\n".join(
                f"{instruction_label}\n{ic_sample[0]}\n\n{output_label_horder}\n{ic_sample[1]['function']}\n\n{output_label_horder_usage}\n{ic_sample[1]['usage']}\n"
                for ic_sample in incontext_samples
            )
            return result

def get_incontext_samples(
    level,
    variant,
    num_samples,
    matching_combos,
    test_shape,
    test_color,
    test_location,
    train_samples,
    incontext_labels,
    SEED

):
    filtered_samples = {}

    if level in ["level-1", "level-2"]:
        if variant in ["forder", "horder", "horder_step"]:
            for combo in train_samples:
                if combo not in matching_combos:
                    if combo not in filtered_samples:
                        filtered_samples[combo] = {}
                    for color, locations in train_samples[combo].items():
                        if color != test_color:
                            if color not in filtered_samples[combo]:
                                filtered_samples[combo][color] = []
                                for location in locations:
                                    if location != test_location:
                                        filtered_samples[combo][color].append(
                                            location
                                        )
        if variant == "horder_adapt":
            filtered_samples[test_shape] = {
                test_color: train_samples[test_shape][test_color]
            }

    incontext_samples = []
    for shape, colors in filtered_samples.items():
        for color, locations in colors.items():
            for location in locations:
                for dialog in train_samples[shape][color][location]:
                    if isinstance(dialog, list):
                        im_samples = []
                        for d_ in dialog:
                            im_samples.append((d_["<Programmer>"], d_["<Editor>"]))
                        incontext_samples.append(im_samples)
                    else:
                        if level == "level-2" and variant == "horder_adapt":
                            instr = dialog["<Programmer>"]
                            instr = instr.split(".")
                            instr = ".".join(instr[2:])
                        else:
                            instr = dialog["<Programmer>"]
                        incontext_samples.append((instr, dialog["<Editor>"]))

    random.seed(SEED)
    if level == "level-2":
        if variant in ["forder", "horder_adapt"]:
            if num_samples:
                num_samples = 1

    if num_samples:
        incontext_samples = random.sample(incontext_samples, num_samples)
    else:
        incontext_samples = []

    if incontext_samples:
        incontext_samples = format_incontext_samples(
            level,
            variant,
            incontext_samples,
            incontext_labels,
        )

    return incontext_samples
