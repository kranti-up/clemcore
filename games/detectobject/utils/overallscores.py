import os
from pathlib import Path

from clemgame import file_utils
GAME_NAME = "detectobject"

def _compute_average(metric_values):
    if len(metric_values) == 0:
        return 0.0
    return round(sum(metric_values) / len(metric_values), 3)


def _compute_metrics(filepath, results):
    model_results = {}

    for model, experiments in results.items():
        model_results[model] = {}
        for exp in experiments:
            num_episodes = len(experiments[exp]["precision"])

            model_results[model][exp] = {
                    "precision": _compute_average(experiments[exp]["precision"]),
                    "recall": _compute_average(experiments[exp]["recall"]),
                    "f1_score": _compute_average(experiments[exp]["f1_score"]),
            }

            model_results[model][exp]["num_episodes"] = num_episodes
            model_results[model][exp]["aborted"] = sum(experiments[exp]["aborted"])

    file_utils.store_game_file(model_results, f"{filepath}/overall_scores.json", GAME_NAME)


def compute_overall_scores(records_path):
    records_path = Path(records_path)

    overall_scores = {model_dir.name: {exp_dir.name: {"precision": [], "recall": [], "f1_score": [], "aborted": []} 
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

                scores = file_utils.load_json(f"{episode_dir}/scores.json", GAME_NAME)
                if not scores or "episode scores" not in scores:
                    continue

                for key in ["precision", "recall", "f1_score"]:
                    overall_scores[model_dir.name][exp_dir.name][key].append(
                        scores["episode scores"][key])

                if scores["episode scores"]["Aborted"]:
                    overall_scores[model_dir.name][exp_dir.name]["aborted"].append(1)

    _compute_metrics(records_path, overall_scores)


def _compute_metrics_update(filepath, results):
    model_results = {}

    for model, experiments in results.items():
        model_results[model] = {}
        for exp in experiments:
            #num_episodes = len(experiments[exp]["nc"])

            nc = sum(experiments[exp]["nc"])
            nt = sum(experiments[exp]["nt"])
            np = sum(experiments[exp]["np"])

            precision = nc / np if np != 0 else 0
            recall = nc / nt if nt != 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0

            model_results[model][exp] = {
                    "precision": round(precision, 3),
                    "recall": round(recall, 3),
                    "f1_score": round(f1, 3)
            }

            #model_results[model][exp]["num_episodes"] = num_episodes
            model_results[model][exp]["aborted"] = sum(experiments[exp]["aborted"])

    file_utils.store_game_file(model_results, f"{filepath}/overall_scores_new.json", GAME_NAME)

def compute_overall_scores_update(records_path, filter, cr_turn):
    records_path = Path(records_path)

    overall_scores = {model_dir.name: {exp_dir.name: {"nc": [], "nt": [], "np": [], "aborted": []} 
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

                scores = file_utils.load_json(f"{episode_dir}/scores.json", GAME_NAME)
                if not scores or "turn scores" not in scores:
                    continue    


                for turn in scores["turn scores"]:
                    if not scores["turn scores"][turn][filter]:
                        continue

                    else:
                        if cr_turn == "before" and cr_turn == scores["turn scores"][turn]["is_cr_turn"]:
                            continue


                    if "Aborted" in scores["turn scores"][turn] and scores["turn scores"][turn]["Aborted"]:
                        overall_scores[model_dir.name][exp_dir.name]["aborted"].append(1)
                        break

                    for key in ["nc", "nt", "np"]:
                        overall_scores[model_dir.name][exp_dir.name][key].append(
                            scores["turn scores"][turn][key])

    _compute_metrics_update(records_path, overall_scores)

if __name__=="__main__":
    #compute_overall_scores(records_path="/Users/kranti/Desktop/codebase/cocobots/clembench/results_abl_do_ic_0/")
    compute_overall_scores_update(records_path="/home/admin/Desktop/codebase/cocobots/detectobject_code/clembench/results/",
                                  filter="individual_property", cr_turn="before")
