
import os

import json

def _compute_precision_recall(fn, fp, tp, base_dir):
    overall_results = {}
    for model in fn:
        print(f"Model: {model}, FN: {fn[model]}, FP: {fp[model]}, TP: {tp[model]}")
        overall_results[model] = {}
        if tp[model] + fp[model] == 0:
            precision = 0
        else:
            precision = tp[model] / (tp[model] + fp[model])

        if tp[model] + fn[model] == 0:
            recall = 0
        else:
            recall = tp[model] / (tp[model] + fn[model])
        if precision + recall == 0:
            f1 = 0
        else:
            f1 = 2 * precision * recall / (precision + recall)
        print(f"Model: {model},\n Precision: {round(precision, 2)},\n Recall: {round(recall, 2)},\n F1: {round(f1,2)}")
        overall_results[model]["precision"] = round(precision, 2)
        overall_results[model]["recall"] = round(recall, 2)
        overall_results[model]["f1"] = round(f1)

    save_file = os.path.join(base_dir, "overall_results.json")
    with open(save_file, "w") as f:
        json.dump(overall_results, f, indent=4)


def compute_scores(base_dir):

    fn = {}
    fp = {}
    tp = {}

    for model in os.listdir(base_dir):
        if model.endswith(".json"):
            continue        
        fn[model] = 0
        fp[model] = 0
        tp[model] = 0
        model_path = os.path.join(base_dir, model)
        for game in os.listdir(model_path):
            game_path = os.path.join(model_path, game)
            for exp in os.listdir(game_path):
                exp_path = os.path.join(game_path, exp)
                for episode in os.listdir(exp_path):
                    if episode.endswith(".json"):
                        continue
                    episode_path = os.path.join(exp_path, episode)
                    for filename in os.listdir(episode_path):
                        if not filename in ["scores.json"]:
                            continue

                        with open(os.path.join(episode_path, filename), "r") as f:
                            scores_data = json.load(f)
                            fn[model] += scores_data["episode scores"]["FN"]
                            fp[model] += scores_data["episode scores"]["FP"]
                            tp[model] += scores_data["episode scores"]["TP"]
                            

    _compute_precision_recall(fn, fp, tp, base_dir)


compute_scores(base_dir="/home/admin/Desktop/codebase/cocobots/detectobject_code/clembench/result_minecraft_test_ic3/")