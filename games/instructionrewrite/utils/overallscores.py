
import os

import json


def _compute_precision_recall(fn, fp, tp):
    overall_results = {}
    for model in fn:
        overall_results[model] = {}
        precision = tp[model] / (tp[model] + fp[model])
        recall = tp[model] / (tp[model] + fn[model])
        f1 = 2 * precision * recall / (precision + recall)
        print("Model: {}, Precision: {}, Recall: {}, F1: {}".format(model, precision, recall, f1))
        overall_results[model]["precision"] = round(precision, 2)
        overall_results[model]["recall"] = round(recall)
        overall_results[model]["f1"] = round(f1)
    with open("overall_results_inst_rewrite.json", "w") as f:
        json.dump(overall_results, f, indent=4)


def compute_scores(base_dir="/home/admin/Desktop/codebase/cocobots/minecraft_clem/clembench/results_instructionrewrite/"):

    fn = {}
    fp = {}
    tp = {}

    for model in os.listdir(base_dir):
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
                            

    _compute_precision_recall(fn, fp, tp)


compute_scores()