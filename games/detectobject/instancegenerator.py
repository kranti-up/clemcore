import argparse
import random
import string


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
            if not tests["experiments"][exp]["TEST_DATA_FILE_NAME"]:
                continue

            #create an experiment
            experiment = self.add_experiment(f"{exp}")

            metadata = {"fashion": tests["experiments"][exp]["SCENE_INFO_METADATA_FASHION"], "furniture": tests["experiments"][exp]["SCENE_INFO_METADATA_FURNITURE"]}
            ps = PrepareSampels(metadata)
            prompt = self.load_template(f"resources/initial_prompts/{tests['experiments'][exp]['PROMPT_FILE_NAME']}")

            dialogues = self.load_json(f"resources/data/{tests['experiments'][exp]['TEST_DATA_FILE_NAME']}")
            for dialogue in dialogues:
                ps.format_dialogue(dialogue)
                scene_info = ps.getdialogue_scene(dialogue)
                scene_info = {"SCENE_INFO":scene_info}

                instance = self.add_game_instance(experiment, game_id)
                instance["dialogue_data"] = {"use_dialogue_context": tests["experiments"][exp]["USE_DIALOGUE_CONTEXT"],
                                             
                                             "total_dialogues": dialogue}

                instance["n_turns"] = len(dialogue)
                instance["prompt"] = self.create_prompt(prompt, **scene_info)
                game_id +=1

        print(f"Generated instances for DetectObject game - {game_id - 1} instances.")

    # an additional method, specific for our example
    def create_prompt(self, prompt: str, **kwargs) -> str:
        """Replace a prompt template with slot values."""
        text = string.Template(prompt).safe_substitute(**kwargs)
        #text = string.Template(prompt)

        return text


if __name__ == "__main__":
    #random.seed(SEED)
    # always call this, which will actually generate and save the JSON file
    DetectObjectInstanceGenerator().generate()