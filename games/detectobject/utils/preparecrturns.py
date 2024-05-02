import os
from pathlib import Path

from clemgame import file_utils
GAME_NAME = "detectobject"



class PrepareCRTurns:
    def __init__(self):
        self.cr_dialogues = {}
        self.total_dialogues = 0
        self.num_episodes = 0

    def prepare(self, model_dir, episode, dialogue, response):
        if model_dir is None or episode is None or dialogue is None or response is None:
            return

        if model_dir not in self.cr_dialogues:
            self.cr_dialogues[model_dir] = {}

        self.total_dialogues += 1
        if "disambiguation_label" in dialogue:
            if dialogue["disambiguation_label"] == 1:
                self.cr_dialogues[model_dir][episode] = {}
                for index, turn in enumerate(dialogue["total_dialogues"]):
                    if turn["disambiguation_label"] == 1:
                        groundtruth_dialogue = turn["groundtruth"]
                        groundtruth_eval = response[str(index+1)]["groundtruth"]
                        prediction = response[str(index+1)]["prediction"]
                        self.cr_dialogues[model_dir][episode][index+1] = {"groundtruth_dialogue": groundtruth_dialogue,
                                                            "groundtruth": groundtruth_eval,
                                                            "prediction": prediction,
                                                            "uapairs": turn["uapairs"],}

    def sort_key(self, name):
        return int(name.split('_')[1])

    def validate_groundtruth(self):
        num_mismatches = {}
        for model in self.cr_dialogues:
            num_mismatches[model] = 0
            for episode in self.cr_dialogues[model]:
                for turn in self.cr_dialogues[model][episode]:
                    if self.cr_dialogues[model][episode][turn]["groundtruth_dialogue"] != self.cr_dialogues[model][episode][turn]["groundtruth"]:
                        print(f"Model: {model}, Episode: {episode}, Turn: {turn}")
                        print(f"Groundtruth Dialogue: {self.cr_dialogues[model][episode][turn]['groundtruth_dialogue']}")
                        print(f"Groundtruth Eval: {self.cr_dialogues[model][episode][turn]['groundtruth']}")
                        print("\n")
                        num_mismatches[model] += 1

        for model in num_mismatches:
            if num_mismatches[model] > 0:
                print(f"Model: {model}, Num mismatches: {num_mismatches[model]}")
                raise Exception("Groundtruth mismatches found")
            

        for model in self.cr_dialogues:
            for episode in self.cr_dialogues[model]:
                for turn in self.cr_dialogues[model][episode]:
                    del self.cr_dialogues[model][episode][turn]["groundtruth_dialogue"]

        #Sort the dialogues
        for model in self.cr_dialogues:
            sorted_keys = sorted(self.cr_dialogues[model].keys(), key=self.sort_key)
            self.cr_dialogues[model] = {key: self.cr_dialogues[model][key] for key in sorted_keys}

    def compare_models_for_cr(self):
        dict_keys = list(self.cr_dialogues.keys())
        model1_key = dict_keys[0]
        model2_key = dict_keys[1]
        subdict1_key = set(self.cr_dialogues[model1_key].keys())
        subdict2_key = set(self.cr_dialogues[model2_key].keys())

        #Compare the keys of the subdicts
        if subdict1_key != subdict2_key:
            print(f"Subdict keys are not equal: {subdict1_key}, {subdict2_key}")
            raise Exception("CR Episodes are not same for the two models")

    def run(self, records_path):
        for model_dir in records_path.iterdir():
            if not model_dir.is_dir():
                continue

            for game_dir in model_dir.iterdir():
                if not game_dir.is_dir():
                    continue

            for exp_dir in game_dir.iterdir():
                if not exp_dir.is_dir():
                    continue

                if "with_cr" in exp_dir.name:
                    continue

                print(f"Processing {exp_dir.name}...")                

                for episode_dir in exp_dir.iterdir():
                    if not episode_dir.is_dir():
                        continue
                    self.num_episodes += 1
                    interactions = file_utils.load_json(f"{episode_dir}/interactions.json", GAME_NAME)
                    if not interactions:
                        continue

                    if "Dialogue" not in interactions or "Evaluation" not in interactions:
                        continue

                    self.prepare(model_dir.name, episode_dir.name, interactions["Dialogue"], interactions["Evaluation"])

        self.validate_groundtruth()
        self.compare_models_for_cr()

        print(f"Num Episodes: {self.num_episodes}, Total dialogues: {self.total_dialogues}")
        for model in self.cr_dialogues:
            print(f"Model: {model}, Episodes: {len(self.cr_dialogues[model])}")
        file_utils.store_game_file(self.cr_dialogues, f"{records_path}/amb_dialogues_withoutcr.json", GAME_NAME)


if __name__=="__main__":
    records_path = "/Users/kranti/Desktop/codebase/cocobots/clembench/results/"
    pcrt = PrepareCRTurns()
    pcrt.run(records_path=Path(records_path))
