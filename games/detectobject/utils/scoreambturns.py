import os
from pathlib import Path

from clemgame import file_utils
GAME_NAME = "detectobject"

def _compute_average(episode_values):
    results = {"precision": 0, "recall": 0, "f1_score": 0}
    for metric in ["precision", "recall", "f1_score"]:
        metric_values = [episode_values[episode][metric] for episode in episode_values if metric in episode_values[episode]]
        if len(metric_values) == 0:
            results[metric] = 0
        else:
            results[metric] = round(sum(metric_values) / len(metric_values), 3)

    return results

def _compute_fp_fn_tp(groundtruth, prediction):
    groundtruth_set = set(groundtruth)
    prediction_set = set(prediction)

    tp = len(groundtruth_set & prediction_set)  # Intersection: items present in both sets
    fn = len(groundtruth_set - prediction_set)  # Difference: items in groundtruth but not in prediction
    fp = len(prediction_set - groundtruth_set)  # Difference: items in prediction but not in groundtruth

    return {"tp": tp, "fn": fn, "fp": fp}

def _compute_precision_recall_f1(tp, fn, fp):
    precision = tp / (tp + fp) if tp + fp > 0 else 0
    recall = tp / (tp + fn) if tp + fn > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0

    return {"precision": precision, "recall": recall, "f1_score": f1}


def _compute_metrics(filepath, results):
    model_results = {}

    for model, episodes in results.items():
        model_results[model] = {}

        num_episodes = len(episodes)

        model_results[model] = _compute_average(episodes)

        model_results[model]["num_episodes"] = num_episodes


    file_utils.store_game_file(model_results, filepath, GAME_NAME)

def compute_amb_turn_scores(amb_turns_results_path, save_file):
    amb_turn_scores = {}

    amb_turn_results = file_utils.load_json(amb_turns_results_path, GAME_NAME)
    for model in amb_turn_results:
        amb_turn_scores[model] = {}
        for episode in amb_turn_results[model]:
            amb_turn_scores[model][episode] = {"tp": 0, "fn": 0, "fp": 0, "precision": 0, "recall": 0, "f1_score": 0}
            for turn in amb_turn_results[model][episode]:
                eval_results = _compute_fp_fn_tp(amb_turn_results[model][episode][turn]["groundtruth"],
                                                 amb_turn_results[model][episode][turn]["prediction"])
                amb_turn_scores[model][episode]["tp"] += eval_results["tp"]
                amb_turn_scores[model][episode]["fn"] += eval_results["fn"]
                amb_turn_scores[model][episode]["fp"] += eval_results["fp"]
            eval_episode = _compute_precision_recall_f1(amb_turn_scores[model][episode]["tp"],
                                                         amb_turn_scores[model][episode]["fn"],
                                                         amb_turn_scores[model][episode]["fp"])
            amb_turn_scores[model][episode]["precision"] = eval_episode["precision"]
            amb_turn_scores[model][episode]["recall"] = eval_episode["recall"]
            amb_turn_scores[model][episode]["f1_score"] = eval_episode["f1_score"]


    _compute_metrics(save_file, amb_turn_scores)



if __name__=="__main__":
    records_path="/Users/kranti/Desktop/codebase/cocobots/clembench/results/"
    for file in ["amb_dialogues_withcr.json", "amb_dialogues_withoutcr.json"]:
        filepath = os.path.join(records_path, file)
        save_file = file.split(".")[0]+"_scores.json"
        save_file = os.path.join(records_path, save_file)
        compute_amb_turn_scores(filepath, save_file)
