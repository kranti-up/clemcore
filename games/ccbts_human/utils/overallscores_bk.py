import os
from pathlib import Path

import json


def _compute_average(metric_values):
    return round(sum(metric_values) / len(metric_values), 3)

def _compute_metrics(results):
    model_results = {}

    for model, experiments in results.items():
        model_results[model] = {}
        for exp in experiments:
            num_episodes = len(experiments[exp]["exact_match"]["precision"])  

            model_results[model][exp] = {
                metric: {
                    "precision": _compute_average(experiments[exp][metric]["precision"]),
                    "recall": _compute_average(experiments[exp][metric]["recall"]),
                    "f1_score": _compute_average(experiments[exp][metric]["f1_score"])
                }
                for metric in experiments[exp] 
            }
            model_results[model][exp]["num_episodes"] = num_episodes

    with open("overall_scores.json", "w") as f:
    #with open("/project/kranti/llm_gm/clembench/results/ccbts/overall_scores.json", "w") as f:
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
    '''
    overall_scores = {model_dir.name: {exp_dir.name: {metric: {"precision": [], "recall": [], "f1_score": []} 
                    for metric in ["exact_match", "codebleu", "exec_score"]}
                    for exp_dir in model_dir.iterdir() if exp_dir.is_dir()}
                    for model_dir in records_path.iterdir() if model_dir.is_dir()}
    '''

    overall_scores = {model_dir.name: {exp_dir.name: {metric: {"precision": [], "recall": [], "f1_score": []} 
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

    #with open("overall_scores_1.json", "w") as f:
    #with open("/project/kranti/llm_gm/clembench/results/ccbts/overall_scores.json", "w") as f:
    #    json.dump(overall_scores, f, indent=4)

    _compute_metrics(overall_scores)

if __name__=="__main__":
    compute_overall_scores(records_path="/home/admin/Desktop/codebase/cocobots/llm_gm/clembench/results/")
    #compute_overall_scores(records_path="/project/kranti/llm_gm/clembench/results/ccbts/records/")
    