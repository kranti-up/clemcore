import copy
import random
import string
from typing import List, Dict, Tuple

from clemgame.clemgame import GameInstanceGenerator
from clemgame import file_utils

# set the name of the game in the script, as you named the directory
# this name will be used everywhere, including in the table of results
GAME_NAME = "todsystem"
# we will create 10 instances for each experiment; vary this as you wish
N_INSTANCES = 100
# if the generation involves randomness, remember to set a random seed
SEED = 123

LANGUAGE = "en"


class TODSystemInstanceGenerator(GameInstanceGenerator):
    def __init__(self, game_name):
        # always do this to initialise GameInstanceGenerator
        super().__init__(game_name)
        self.game_name = game_name


    def _prepare_prompts(self, goal: str):
        prompt_file_names = {
            "initial_prompt_a": "prompt_a",
            "turn_prompt_a": "turn_prompt_a",
        }

        promptsdict = {}
        for file_name, match_key in prompt_file_names.items():
            filedata = file_utils.load_template(
                f"resources/initial_prompts/{LANGUAGE}/{file_name}", GAME_NAME
            )
            promptsdict[match_key] = self.create_prompt(goal, filedata)

        return promptsdict

    # define on_generate, a mandatory method
    def on_generate(self):
        num_instances = 0


        taskdialogs = file_utils.load_json(
            f"resources/tasks/{LANGUAGE}/taskdata_dev.json", GAME_NAME
        )
        config = file_utils.load_json(
            f"resources/config/{LANGUAGE}/taskconfig.json", GAME_NAME
        )

        tot_instances = 0
        game_ids = random.sample(range(len(taskdialogs)), N_INSTANCES)        
        for tsystem in config["todsystems"]:
            experiment = self.add_experiment(tsystem)
            #for game_id in range(len(taskdialogs)):
            for game_id in game_ids:
                if config["data_split"] != taskdialogs[game_id]["data_split"]:
                    continue

                if not any(topic in taskdialogs[game_id]["domains"] for topic in config["topics"]):
                    continue

                promptsdict = self._prepare_prompts(taskdialogs[game_id]["message"])
                instance = self.add_game_instance(experiment, game_id)
                instance["data"] = dict(taskdialogs[game_id])
                instance["data"]["db_path"] = f"games/todsystem/resources/data/{LANGUAGE}/multiwoz"#"games/todsystem/dialogue_systems/data/multiwoz"
                instance["data"]["prompts"] = promptsdict
                instance["data"]["tsystem"] = tsystem
                instance["data"]["statusmsg"] = config["statusmsg"]
                instance["data"]["n_turns"] = config["n_turns"]
                num_instances += 1
            tot_instances += num_instances

        print(
            f"Generated instances for -{self.game_name} game - {len(config['todsystems']) * N_INSTANCES} instances."
        )

    # an additional method, specific for our example
    def create_prompt(self, goal: str, prompt: str) -> str:
        """Replace a prompt template with slot values."""
        text = string.Template(prompt).substitute(goal=goal)
        return text


if __name__ == "__main__":
    random.seed(SEED)
    # always call this, which will actually generate and save the JSON file
    TODSystemInstanceGenerator(GAME_NAME).generate()
