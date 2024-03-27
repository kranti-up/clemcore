def _extract_and_compare(key, ground_truth, prediction):
    if key in ground_truth and key in prediction:
        if ground_truth[key]:
            if key in prediction and prediction[key]:
                gt_items = [line.strip() for line in ground_truth[key].split("\n") if line.strip()]
                gen_items_base = [line.strip() for line in prediction[key].split("\n") if line.strip()]
                gen_items = []
                for line in gen_items_base:
                    if ":" in line:
                        line = line.split(":")[1]
                    gen_items.append(line.strip())
                        
                return gt_items == gen_items
            else:
                return False
    return True

def em_comparison(ground_truth, prediction, results_counter):
  
    if (
        isinstance(ground_truth, str)
        and isinstance(prediction, str)
        or isinstance(ground_truth, list)
        and isinstance(prediction, list)
    ):
        em_match_type = "success" if ground_truth == prediction else "failure"

    elif isinstance(ground_truth, dict) and isinstance(prediction, dict):
        output_match_type = _extract_and_compare("output", ground_truth, prediction)
        func_match_type = _extract_and_compare("function", ground_truth, prediction)
        usage_match_type = _extract_and_compare("usage", ground_truth, prediction)

        print(f"output_match_type: {output_match_type} func_match_type: {func_match_type} usage_match_type: {usage_match_type}")

        em_match_type = output_match_type and func_match_type and usage_match_type
        em_match_type = "success" if em_match_type else "failure"

    else:
        em_match_type = "failure"


    results_counter[em_match_type] += 1
    return em_match_type