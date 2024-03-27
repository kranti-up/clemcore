from codebleu import calc_codebleu

def _get_codebleu_score(ground_truth, generated_code):
    codeblue_results = calc_codebleu(
        ground_truth,
        generated_code,
        lang="python",
        weights=(0.25, 0.25, 0.25, 0.25),
        tokenizer=None,
    )
    codebleu_score = [
        "codebleu",
        "ngram_match_score",
        "weighted_ngram_match_score",
        "syntax_match_score",
        "dataflow_match_score",
    ]
    for score in codebleu_score:
        codeblue_results[score] = round(codeblue_results[score], 3)

    match_result = "success" if codeblue_results["codebleu"] > 0.5 else "failure"
    return match_result, codeblue_results


def cb_comparison(ground_truth, prediction, results):

    cb_result = {}
    for code_type in ground_truth:
        if code_type not in prediction:
            continue

        gt = ground_truth[code_type]
        if not gt:
            continue

        cb_result[code_type] = {"status": None, "scores": ""}            

        gen = prediction[code_type]
        if isinstance(gt, str):
            gt = [gt]
        if  isinstance(gen, str):
            gen = [gen]

        if not gen or len(gt) != len(gen):
            cb_result[code_type]["status"] = "failure"
            cb_result[code_type]["scores"] = {
                "codebleu": None,
                "ngram_match_score": None,
                "weighted_ngram_match_score": None,
                "syntax_match_score": None,
                "dataflow_match_score": None,
            }
        else:
            cb_result[code_type]["status"], cb_result[code_type]["scores"] = _get_codebleu_score(gt, gen)
            
        #iterate through cb_result and check if all are success
        cb_match_type = "success" if all([cb_result[eval_type]["status"] == "success" for eval_type in cb_result]) else "failure"
        

    results[cb_match_type] += 1
    results["scores"] = cb_result

    return cb_match_type