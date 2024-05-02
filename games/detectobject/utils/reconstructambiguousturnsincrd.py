import os
from pathlib import Path

from clemgame import file_utils
GAME_NAME = "detectobject"


class ReconstructAbTurns:
    def __init__(self, filename):
        self.basecr_turn_filename = filename
        self.cr_dialogues = {}
        self.total_dialogues = 0
        self.num_episodes = 0
        self.base_cr = self.read_base_file()


    def read_base_file(self):
        return file_utils.load_json(self.basecr_turn_filename, GAME_NAME)

    def reconstruct(self, model_dir, episode, response):
        if model_dir is None or episode is None or response is None:
            return
        
        if model_dir not in self.base_cr:
            print(f"Model: {model_dir} not found in base_cr")

        if model_dir not in self.cr_dialogues:
            self.cr_dialogues[model_dir] = {}

        if episode in self.base_cr[model_dir]:
            self.cr_dialogues[model_dir][episode] = {}
            for turn in self.base_cr[model_dir][episode]:
                self.cr_dialogues[model_dir][episode][turn] = {"groundtruth": response[turn]["groundtruth"],
                                                                "prediction": response[turn]["prediction"],}

    def sort_key(self, name):
        return int(name.split('_')[1])

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

                if "without_cr" in exp_dir.name:
                    continue

                print(f"Processing {exp_dir.name}...")                

                for episode_dir in exp_dir.iterdir():
                    if not episode_dir.is_dir():
                        continue

                    self.num_episodes += 1
                    interactions = file_utils.load_json(f"{episode_dir}/interactions.json", GAME_NAME)
                    if not interactions:
                        continue

                    if "Evaluation" not in interactions:
                        continue

                    self.reconstruct(model_dir.name, episode_dir.name, interactions["Evaluation"])

                    
        print(f"Number of episodes: {self.num_episodes}")
        for model in self.cr_dialogues:
            print(f"Model: {model}, Episodes: {len(self.cr_dialogues[model])}")
            sorted_keys = sorted(self.cr_dialogues[model].keys(), key=self.sort_key)
            self.cr_dialogues[model] = {key: self.cr_dialogues[model][key] for key in sorted_keys}


        file_utils.store_game_file(self.cr_dialogues, f"{records_path}/amb_dialogues_withcr.json", GAME_NAME)





if __name__=="__main__":
    records_path = "/Users/kranti/Desktop/codebase/cocobots/clembench/results/"
    base_cr_turns = os.path.join(records_path, "amb_dialogues_withoutcr.json")
    rabt = ReconstructAbTurns(base_cr_turns)
    rabt.run(records_path=Path(records_path))


