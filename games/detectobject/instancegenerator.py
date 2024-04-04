import random
import string

from clemgame.clemgame import GameInstanceGenerator

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

    # an additional method, specific for our example
    def create_prompt(self, prompt: str, **kwargs) -> str:
        """Replace a prompt template with slot values."""
        text = string.Template(prompt).safe_substitute(**kwargs)

        return text


if __name__ == "__main__":
    #random.seed(SEED)
    # always call this, which will actually generate and save the JSON file
    DetectObjectInstanceGenerator().generate()