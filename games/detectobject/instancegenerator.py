import argparse
import random
import string
import re


from clemgame.clemgame import GameInstanceGenerator
from games.detectobject.utils.preparesamplesinfo import PrepareSampels


# set the name of the game in the script, as you named the directory
# this name will be used everywhere, including in the table of results
GAME_NAME = "detectobject"
# we will create 10 instances for each experiment; vary this as you wish
N_INSTANCES = 10
# if the generation involves randomness, remember to set a random seed
SEED = "42"


class DetectObjectInstanceGenerator(GameInstanceGenerator):
    def __init__(self):
        # always do this to initialise GameInstanceGenerator
        super().__init__(GAME_NAME)

    # define on_generate, a mandatory method
    def on_generate(self):
        # get the list of topics, which will be our experiments
        tests = self.load_json("resources/tests.json")

        game_id = 1
        for exp in tests["experiments"]:
            if exp != "all_turns":
                continue
            if not tests["experiments"][exp]["TEST_DATA_FILE_NAME"]:
                continue

            #create an experiment
            experiment = self.add_experiment(f"{exp}")

            metadata = {"fashion": tests["experiments"][exp]["SCENE_INFO_METADATA_FASHION"], "furniture": tests["experiments"][exp]["SCENE_INFO_METADATA_FURNITURE"]}
            scene_info_file_name = tests["experiments"][exp]["TEST_SCENE_FILE_NAME"]
            ps = PrepareSampels(metadata, scene_info_file_name)
            prompt = self.load_template(f"resources/initial_prompts/{tests['experiments'][exp]['PROMPT_FILE_NAME']}")

            dialogues = self.load_json(f"resources/data/{tests['experiments'][exp]['TEST_DATA_FILE_NAME']}")
            for turn in dialogues:
                ps.format_dialogue(turn)
                scene_info = ps.getdialogue_scene(turn)
                history_details = ps.format_history(turn["history"])
                if turn["history"]:
                    details_to_fill = {"SCENE_INFO":scene_info, "DIALOGUE_HISTORY": history_details}
                else:
                    details_to_fill = {"SCENE_INFO":scene_info}
                #disambiguaion_label = ps.getdisambiguationlabel(dialogue)

                instance = self.add_game_instance(experiment, game_id)
                instance["dialogue_data"] = {"history": history_details,
                                             "utterance": f"User: {turn['utterance']}",
                                             "is_cr_turn": turn["is_cr_turn"],
                                             "individual_property": turn["individual_property"],
                                             "dialogue_history": turn["dialogue_history"],
                                             "relational_context": turn["relational_context"],
                                             "groundtruth": turn["groundtruth"],
                                             "scene_ids": turn["scene_ids"]}

                instance["n_turns"] = 1
                instance["prompt"] = self.create_prompt(prompt, **details_to_fill)
                game_id +=1

        print(f"Generated instances for DetectObject game - {game_id - 1} instances.")

    # an additional method, specific for our example
    def create_prompt(self, prompt: str, **kwargs) -> str:
        """Replace a prompt template with slot values."""
        text = string.Template(prompt)
        text = text.safe_substitute(**kwargs)
        text = re.sub(r'\$\w+', '', text)


        #text = string.Template(prompt).safe_substitute(**kwargs)
        #text = string.Template(prompt)

        return text


if __name__ == "__main__":
    #random.seed(SEED)
    # always call this, which will actually generate and save the JSON file
    DetectObjectInstanceGenerator().generate()