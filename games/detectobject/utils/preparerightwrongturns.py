import os
from pathlib import Path

from clemgame import file_utils
GAME_NAME = "detectobject"


class PrepareRightWrongTurns:
    def __init__(self):
        pass


    def run(self, base_records_path, file_to_process, save_file_name):
        results = {}
        data = file_utils.load_json(file_to_process, GAME_NAME)
        print(f"Processing {file_to_process}")
        for model in data:
            results[model] = {"correct": {}, "incorrect": {}}

            num_episodes = 0
            num_turns = 0
            num_correct = 0
            num_wrong = 0
            for episode in data[model]:
                num_episodes += 1
                for turn in data[model][episode]:
                    num_turns += 1
                    groundtruth = set(data[model][episode][turn]["groundtruth"])
                    prediction = set(data[model][episode][turn]["prediction"])
                    if groundtruth == prediction:
                        num_correct += 1
                        if episode not in results[model]["correct"]:
                            results[model]["correct"][episode] = {}
                        results[model]["correct"][episode][turn] = data[model][episode][turn]
                    else:
                        num_wrong += 1
                        if episode not in results[model]["incorrect"]:
                            results[model]["incorrect"][episode] = {}
                        results[model]["incorrect"][episode][turn] = data[model][episode][turn]

            model_episode_keys = set(data[model].keys())
            correct_episode_keys = set(results[model]["correct"].keys())
            incorrect_episode_keys = set(results[model]["incorrect"].keys())

            if correct_episode_keys - model_episode_keys:
                print("Correct episodes has more than model episodes", len(correct_episode_keys - model_episode_keys))
                raise Exception("Correct episodes has more than model episodes")

            if incorrect_episode_keys - model_episode_keys:
                print("Incorrect episodes has more than in model episodes", len(incorrect_episode_keys - model_episode_keys))
                raise Exception("Incorrect episodes has more than in model episodes")


            print(f"Model: {model}, NumEpisodes: {num_episodes}, NumTurns: {num_turns}")

            #print(f"Correct NumEpisodes: {len(results[model]['correct'].keys())}, num_correct = {num_correct}")
            #print(f"Incorrect NumEpisodes: {len(results[model]['incorrect'].keys())}, num_wrong = {num_wrong}")

            num_turns_count_cor = sum(len(turns) for turns in results[model]['correct'].values())
            num_turns_count_inc = sum(len(turns) for turns in results[model]['incorrect'].values())

            print(f"Correct NumTurns: {num_turns_count_cor}, Incorrect NumTurns: {num_turns_count_inc}")

        file_utils.store_game_file(results, f"{base_records_path}/{save_file_name}", GAME_NAME)

    def compare(self, base_record_path, without_cr_rightwrong_file, with_cr_rightwrong_file):
        without_cr = file_utils.load_json(f"{base_record_path}/{without_cr_rightwrong_file}", GAME_NAME)
        with_cr = file_utils.load_json(f"{base_record_path}/{with_cr_rightwrong_file}", GAME_NAME)

        analysis = {}
        for model in without_cr:
            num_pos_impact = 0
            num_neg_impact = 0
            num_no_impact_correct = 0
            num_no_impact_incorrect = 0
            if model not in with_cr:
                print(f"Model: {model} not found in with_cr")
                continue

            analysis[model] = {"neg_impact": {}, "pos_impact": {}, "no_impact_correct": {}, "no_impact_incorrect": {}}

            for episode in without_cr[model]["correct"]:
                if episode in with_cr[model]["correct"]:
                    without_cr_turns = set(without_cr[model]["correct"][episode].keys())
                    with_cr_turns = set(with_cr[model]["correct"][episode].keys())

                    neg_impact_turns = without_cr_turns - with_cr_turns
                    num_neg_impact += len(neg_impact_turns)                    
                    if episode not in analysis[model]["neg_impact"]:
                        analysis[model]["neg_impact"][episode] = {}

                    for turn in neg_impact_turns:
                        analysis[model]["neg_impact"][episode][turn] = without_cr[model]["correct"][episode][turn]
                    #Don't add positive impact here, this gets added in incorrect vs correct comparison
                    #num_pos_impact += len(with_cr_turns - without_cr_turns)
                    non_impact_correct_turns = without_cr_turns & with_cr_turns
                    num_no_impact_correct += len(non_impact_correct_turns)
                    if episode not in analysis[model]["no_impact_correct"]:
                        analysis[model]["no_impact_correct"][episode] = {}

                    for turn in non_impact_correct_turns:
                        analysis[model]["no_impact_correct"][episode] = without_cr[model]["correct"][episode][turn]


                if episode in with_cr[model]["incorrect"]:
                    without_cr_turns = set(without_cr[model]["correct"][episode].keys())
                    with_cr_turns = set(with_cr[model]["incorrect"][episode].keys())

                    neg_impact_turns = without_cr_turns & with_cr_turns
                    num_neg_impact += len(neg_impact_turns)
                    if episode not in analysis[model]["neg_impact"]:
                        analysis[model]["neg_impact"][episode] = {}

                    for turn in neg_impact_turns:
                        analysis[model]["neg_impact"][episode][turn] = without_cr[model]["correct"][episode][turn]

            for episode in without_cr[model]["incorrect"]:
                if episode in with_cr[model]["incorrect"]:
                    without_cr_turns = set(without_cr[model]["incorrect"][episode].keys())
                    with_cr_turns = set(with_cr[model]["incorrect"][episode].keys())
                    non_impact_correct_turns = without_cr_turns & with_cr_turns
                    num_no_impact_incorrect += len(non_impact_correct_turns)
                    if episode not in analysis[model]["no_impact_incorrect"]:
                        analysis[model]["no_impact_incorrect"][episode] = {}

                    for turn in non_impact_correct_turns:
                        analysis[model]["no_impact_incorrect"][episode] = without_cr[model]["incorrect"][episode][turn]

                if episode in with_cr[model]["correct"]:
                    without_cr_turns = set(without_cr[model]["incorrect"][episode].keys())
                    with_cr_turns = set(with_cr[model]["correct"][episode].keys())

                    pos_impact_turns = with_cr_turns & without_cr_turns
                    num_pos_impact += len(pos_impact_turns)
                    if episode not in analysis[model]["pos_impact"]:
                        analysis[model]["pos_impact"][episode] = {}

                    for turn in pos_impact_turns:
                        analysis[model]["pos_impact"][episode][turn] = with_cr[model]["correct"][episode][turn]


            print(f"Model: {model}")
            #print(f"WithoutCR_Correct NumTurns: {sum(len(turns) for turns in without_cr[model]['correct'].values())}")
            #print(f"WithoutCR_Incorrect NumTurns: {sum(len(turns) for turns in without_cr[model]['incorrect'].values())}")
            #print(f"WithCR_Correct NumTurns: {sum(len(turns) for turns in with_cr[model]['correct'].values())}")
            #print(f"WithCR_Incorrect NumTurns: {sum(len(turns) for turns in with_cr[model]['incorrect'].values())}")

            print(f"NumNegImpact: {num_neg_impact}, NumPosImpact: {num_pos_impact}, NumNoImpactCorrect: {num_no_impact_correct}, NumNoImpactIncorrect: {num_no_impact_incorrect}")
        file_utils.store_game_file(analysis, f"{base_record_path}/analysis.json", GAME_NAME)


if __name__=="__main__":
    prwt = PrepareRightWrongTurns()
    records_path="/Users/kranti/Desktop/codebase/cocobots/clembench/results/"
    for file in ["amb_dialogues_withcr.json", "amb_dialogues_withoutcr.json"]:
        filepath = os.path.join(records_path, file)
        save_file = file.split(".")[0]+"_rightwrong.json"
        prwt.run(records_path, filepath, save_file)

    prwt.compare(records_path, "amb_dialogues_withoutcr_rightwrong.json", "amb_dialogues_withcr_rightwrong.json")
        
