import os
import numpy as np
import json

from games.clemtod.utils import processgenslots

def _setto_lower(slots: dict) -> dict:
    return {
            str(domain).lower(): {str(key).lower(): str(value).lower() for key, value in dvalue.items()}
            for domain, dvalue in slots.items()
        }

def _compare_slots(gt_slots: dict, gen_slots: dict):

    if not gt_slots:
        return False, "Ground truth slots are empty"
    
    if not gen_slots:
        return False, "Generated slots are empty"

    gtcompslots = _setto_lower(gt_slots)
    gencompslots = _setto_lower(gen_slots)
    #print(gtcompslots)
    #print(gencompslots)

    missed_domains = [domain for domain in gtcompslots if domain not in gencompslots]
    if missed_domains:
        #print(f"Domains of the ground truth slots and generated do not match {missed_domains}")
        return False, missed_domains

    missed_values = []
    for domain, dvalue in gtcompslots.items():
        missed_keys = [key for key in dvalue if key not in gencompslots[domain]]
        if missed_keys:
            #print(f"Keys of the ground truth slots and generated slots do not match {missed_keys}")
            return False, [{domain:missed_keys}]
        
        mvalues = [
            {key: {"gt": value, "gen": gencompslots[domain][key]}}
            for key, value in dvalue.items()
            if value != gencompslots[domain][key]
        ]
        if mvalues:
            missed_values.append({domain: mvalues})

    if missed_values:
        #print(f"Values of the ground truth slots and generated slots do not match {missed_values}")
        return False, missed_values                      
    
    return True, None

def processgenslots_old(gen_slots: dict) -> dict:
    modgen_slots = {}
    for key, data in gen_slots.items():
        if key == "train":
            if key not in modgen_slots:
                modgen_slots[key] = {}
            for k, v in data.items():
                if k == "tickets":
                    modgen_slots[key]["bookpeople"] = v
                else:
                    modgen_slots[key][k] = v
        elif key == "restaurant":
            if key not in modgen_slots:
                modgen_slots[key] = {}

            for k, v in data.items():
                if k == "people":
                    modgen_slots[key]["bookpeople"] = v
                elif k == "time":
                    modgen_slots[key]["booktime"] = v
                elif k == "day":
                    modgen_slots[key]["bookday"] = v
                else:
                    modgen_slots[key][k] = v
        elif key == "hotel":
            if key not in modgen_slots:
                modgen_slots[key] = {}

            for k, v in data.items():
                if k == "people":
                    modgen_slots[key]["bookpeople"] = v
                elif k == "stay":
                    modgen_slots[key]["bookstay"] = v
                elif k == "day":
                    modgen_slots[key]["bookday"] = v
        else:
            modgen_slots[key] = data

    return modgen_slots


def getslotvaluesbycategories(slots: dict):
        infoslots = {}
        attrslots = {}
        bookslots = {}

        for domain, dvalue in slots.items():
            for key, kvalue in dvalue.items():
                if key == "info":
                    if domain not in infoslots:
                        infoslots[domain] = {}

                    for k, v in kvalue.items():
                        infoslots[domain][k] = v

                elif key == "book":
                    if domain not in bookslots:
                        bookslots[domain] = {}

                    for k, v in kvalue.items():
                        if k in ["invalid", "pre_invalid"]:
                            continue
                        bookslots[domain][f"book{k}"] = v

                elif key == "reqt":
                    if domain not in attrslots:
                        attrslots[domain] = {}
                    
                    attrslots[domain] = kvalue
                else:
                    continue

        return infoslots, bookslots, attrslots

def _extract_dialogue(interaction_data):
    turn_data = interaction_data["turns"]

    dialogue = []

    for turn in turn_data:
        for item in turn:
            if item["from"] == "Player 1" and item["to"] == "GM":
                if "action" in item and item["action"]["type"] == "get message":
                    dialogue.append({"user": item["action"]["content"]})

            elif item["from"] == "Player 2" and item["to"] == "GM":
                if "action" in item and item["action"]["type"] == "get message":
                    dialogue[-1].update({"system":item["action"]["content"]})

    return dialogue






def compute_scores(base_dir):
    results = {}

    for model in os.listdir(base_dir):
        if model.endswith(".json"):
            continue
        model_path = os.path.join(base_dir, model)
        for game in os.listdir(model_path):
            if game not in results:
                results[game] = {}
            if model not in results[game]:
                results[game][model] = {}
            game_path = os.path.join(model_path, game)
            for exp in os.listdir(game_path):
                if exp not in results[game][model]:
                    results[game][model][exp] = {}
                exp_path = os.path.join(game_path, exp)

                if exp_path.endswith(".json") or not os.path.isdir(exp_path):
                    continue

                num_episodes = 0
                info_only_results = {}
                info_book_results = {}
                info_attr_results = {}
                info_book_attr_results = {}
                for episode in os.listdir(exp_path):
                    if episode.endswith(".json"):
                        continue
                    num_episodes += 1
                    episode_path = os.path.join(exp_path, episode)
                    for filename in os.listdir(episode_path):
                        if not filename in ["interactions.json"]:
                            continue

                        with open(os.path.join(episode_path, filename), "r") as f:
                            interaction_data = json.load(f)


                        generated_dialogue = interaction_data["Evaluation"]["gendialogue"]#_extract_dialogue(interaction_data)
                        with open(os.path.join(episode_path, "dialogue.json"), "w", encoding="utf-8") as f:
                            json.dump(generated_dialogue, f, ensure_ascii=False, indent=4)

                        game_evaldata = interaction_data["Evaluation"]

                        dialogue_type = game_evaldata["dialogue_type"]
                        domains = game_evaldata["domains"]
                        tsystem = game_evaldata["tsystem"]
                        play_turns = game_evaldata["play_turns"]
                        n_turns = game_evaldata["n_turns"]
                        gameresult_lose = interaction_data["Lose"]
                        corpususer = game_evaldata["corpususer"]
                        gt_slots = game_evaldata["slots_gt"]
                        gen_slots = game_evaldata["slots_gen"]
                        if gen_slots:
                            gen_slots_processed = processgenslots(gen_slots)
                        else:
                            gen_slots_processed = {}
                        if "slots_gen_loss" in game_evaldata:
                            gen_slots_loss = game_evaldata["slots_gen_loss"]
                        else:
                            gen_slots_loss = {}

                        data_to_save = {"play_turns": play_turns,
                                        "n_turns": n_turns,
                                        "dialogue_type": dialogue_type,
                                        "domains": domains,
                                        }

                        infoslots_gt, bookslots_gt, attrslots_gt = getslotvaluesbycategories(gt_slots)
                        if game_evaldata["tasktype"] == "info_book":
                            use_metric_list = info_book_results
                        elif game_evaldata["tasktype"] == "info_attr":
                            use_metric_list = info_attr_results
                        elif game_evaldata["tasktype"] == "info_book_attr":
                            use_metric_list = info_book_attr_results

                        labels = ["generated"]#, "lossgen"]


                        for label, gendata in zip(labels, [gen_slots_processed]):
                            if label not in use_metric_list:
                                use_metric_list[label] = []
                            
                            status, _ = _compare_slots(infoslots_gt, gendata)
                            if status:
                                use_metric_list[label].append({"entity": 1})
                                if bookslots_gt:
                                    status, _ = _compare_slots(bookslots_gt, gendata)
                                    if status:
                                        use_metric_list[label][-1].update({"tasksuccess": 1})
                                    else:
                                        use_metric_list[label][-1].update({"tasksuccess": 0})
                            else:
                                use_metric_list[label].append({"entity": 0, "tasksuccess": 0})

                results[game][model][exp]["num_episodes"] = num_episodes
                def calculate_metrics(results_list, key):
                    if results_list:
                        inform_episode = [episode["entity"] for episode in results_list["generated"]]
                        entity = np.mean(inform_episode) if inform_episode else 0.0
                        entity = round(entity, 2)
                        metrics = {"num_episode": len(inform_episode),
                                   #"entity_list": inform_episode,
                                   "entity": entity}
                        if key in ["info_book", "info_book_attr"]:
                            book_episode = [episode["tasksuccess"] for episode in results_list["generated"]]
                            tasksuccess = np.mean(book_episode) if book_episode else 0.0
                            tasksuccess = round(tasksuccess, 2)
                            metrics.update({#"tasksuccess_list": book_episode,
                                            "tasksuccess": tasksuccess})
                        results[game][model][exp][key] = metrics

                calculate_metrics(info_only_results, "info_only")
                calculate_metrics(info_book_results, "info_book")
                calculate_metrics(info_attr_results, "info_attr")
                calculate_metrics(info_book_attr_results, "info_book_attr")

        
            #Compute the overall entity and task success results for the model
            results[game][model]["overall"] = {}
            overall_entity = []
            overall_tasksuccess = []

            for exp in results[game][model]:
                if exp == "overall":
                    continue
                if "info_only" in results[game][model][exp]:
                    overall_entity.append(results[game][model][exp]["info_only"]["entity"])
                if "info_book" in results[game][model][exp]:
                    overall_entity.append(results[game][model][exp]["info_book"]["entity"])
                    overall_tasksuccess.append(results[game][model][exp]["info_book"]["tasksuccess"])
                if "info_attr" in results[game][model][exp]:
                    overall_entity.append(results[game][model][exp]["info_attr"]["entity"])
                if "info_book_attr" in results[game][model][exp]:
                    overall_entity.append(results[game][model][exp]["info_book_attr"]["entity"])
                    overall_tasksuccess.append(results[game][model][exp]["info_book_attr"]["tasksuccess"])

            results[game][model]["overall"]["entity"] = {"num_systems": len(overall_entity),
                                                         "value": round(np.mean(overall_entity), 2) }
            results[game][model]["overall"]["tasksuccess"] = {"num_systems": len(overall_tasksuccess),
                                                              "value": round(np.mean(overall_tasksuccess), 2)}
    #print(results)

    with open(os.path.join(base_dir, "taskmetrics.json"), "w") as f:
        json.dump(results, f, indent=2)

    print("Task metrics computed and saved to taskmetrics.json")


compute_scores(
    "/home/admin/Desktop/codebase/cocobots/clembenchfork_dm_code/clembench/results_test_llama370b_single_hetal"
)
