import os
from pathlib import Path

import json


def _update_error_analysis(fail_reason, model_results, use_key):
    for model, experiments in fail_reason.items():
        for exp in experiments:
            model_results[model][exp][use_key] = {}
            for reason in experiments[exp]:
                if reason in model_results[model][exp][use_key]:
                    model_results[model][exp][use_key][reason] += 1
                else:
                    model_results[model][exp][use_key][reason] = 1

def _compute_average(metric_values):
    if len(metric_values) == 0:
        return 0.0
    return round(sum(metric_values) / len(metric_values), 3)

def _compute_metrics(filepath, results):
    model_results = {}
    fail_reason = {}
    detail_error = {}

    for model, experiments in results.items():
        model_results[model] = {}
        fail_reason[model] = {}
        detail_error[model] = {}
        for exp in experiments:
            num_episodes = len(experiments[exp]["exact_match"]["precision"])


            model_results[model][exp] = {
                metric: {
                    "precision": _compute_average(experiments[exp][metric]["precision"]),
                    "recall": _compute_average(experiments[exp][metric]["recall"]),
                    "f1_score": _compute_average(experiments[exp][metric]["f1_score"]),
                }
                for metric in experiments[exp] if metric not in ["fail_reason", "detail_error"]
            }

            fail_reason[model][exp] = []
            fail_reason[model][exp].extend(experiments[exp]["fail_reason"])

            detail_error[model][exp] = []
            detail_error[model][exp].extend(experiments[exp]["detail_error"])

            model_results[model][exp]["num_episodes"] = num_episodes
            model_results[model][exp]["success"] = sum(experiments[exp]["exec_score"]["success"])
            model_results[model][exp]["failure"] = sum(experiments[exp]["exec_score"]["failure"])
            model_results[model][exp]["aborted"] = sum(experiments[exp]["exec_score"]["aborted"])

            #print(f"Model: {model}, Experiment: {exp} ExecScore: {experiments[exp]['exec_score']['f1_score']}, Success:{model_results[model][exp]['success']} ")
            #input()

    _update_error_analysis(fail_reason, model_results, "fail_reason")
    _update_error_analysis(detail_error, model_results, "detail_error")

    #with open("overall_scores.json", "w") as f:
    #with open("/Users/kranti/Desktop/codebase/cocobots/clembench/results_ablation_cdlm7b_sb_so_ic_6/overall_scores.json", "w") as f:
    with open(f"{filepath}/overall_scores.json", "w") as f:
        json.dump(model_results, f, indent=4)


def load_scores(file_path):
    try:
        with file_path.open('r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"No scores.json found in {file_path}")
        return None
    
def compute_overall_scores(records_path):
    records_path = Path(records_path)

    overall_scores = {model_dir.name: {exp_dir.name: {metric: {"success": [], "failure":[], "precision": [], "recall": [], "f1_score": [], "aborted": []} 
                     for metric in ["exact_match", "codebleu", "exec_score"]}
                     for game_dir in model_dir.iterdir() if game_dir.is_dir()
                 for exp_dir in game_dir.iterdir() if exp_dir.is_dir()}
                     for model_dir in records_path.iterdir() if model_dir.is_dir()}

    for model_dir in records_path.iterdir():
        if not model_dir.is_dir():
            continue

        for game_dir in model_dir.iterdir():
            if not game_dir.is_dir():
                continue

        for exp_dir in game_dir.iterdir():
            if not exp_dir.is_dir():
                continue

            overall_scores[model_dir.name][exp_dir.name]["fail_reason"] = []
            overall_scores[model_dir.name][exp_dir.name]["detail_error"] = []


            for episode_dir in exp_dir.iterdir():
                if not episode_dir.is_dir():
                    continue

                scores = load_scores(episode_dir / "scores.json")
                if not scores or "episode scores" not in scores:
                    continue

                for metric in ["exact_match", "codebleu", "exec_score"]:
                    if metric not in scores["episode scores"]:
                        print(f"No {metric} found in {episode_dir}")
                        continue

                    for key in ["precision", "recall", "f1_score"]:
                        overall_scores[model_dir.name][exp_dir.name][metric][key].append(
                            scores["episode scores"][metric][key])
                    if "success" in scores["episode scores"][metric]:
                        overall_scores[model_dir.name][exp_dir.name][metric]["success"].append(1)
                    elif "failure" in scores["episode scores"][metric]:
                        overall_scores[model_dir.name][exp_dir.name][metric]["failure"].append(1)
                    else:
                        if scores["episode scores"]["Aborted"]:
                            overall_scores[model_dir.name][exp_dir.name][metric]["aborted"].append(1)

                if "exec_result" in scores["episode scores"]:
                    fail_reasons = []
                    detail_errors = []
                    for turn in scores["episode scores"]["exec_result"]:
                        fail_reasons.append(scores["episode scores"]["exec_result"][turn]["fail_reason"])
                        detail_errors.append(scores["episode scores"]["exec_result"][turn]["detail_error"])

                    overall_scores[model_dir.name][exp_dir.name]["fail_reason"].extend(fail_reasons)
                    overall_scores[model_dir.name][exp_dir.name]["detail_error"].extend(detail_errors)


    #with open("overall_scores_1.json", "w") as f:
    #with open("/project/kranti/llm_gm/clembench/results/ccbts/overall_scores.json", "w") as f:
    #    json.dump(overall_scores, f, indent=4)

    _compute_metrics(records_path, overall_scores)

if __name__=="__main__":
    compute_overall_scores(records_path="/Users/kranti/Desktop/codebase/cocobots/clembench/results/")
    #compute_overall_scores(records_path="/project/kranti/llm_gm/clembench/results/ccbts/records/")
    