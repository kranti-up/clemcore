import random
import string

from clemgame.clemgame import GameInstanceGenerator

# set the name of the game in the script, as you named the directory
# this name will be used everywhere, including in the table of results
GAME_NAME = 'minecraft'
# we will create 10 instances for each experiment; vary this as you wish
N_INSTANCES = 10
# if the generation involves randomness, remember to set a random seed
SEED = 123

class MinecraftGameInstanceGenerator(GameInstanceGenerator):
    def __init__(self):
        # always do this to initialise GameInstanceGenerator
        super().__init__(GAME_NAME)


    # define on_generate, a mandatory method
    def on_generate(self):

        prompt_a = self.load_template('resources/initial_prompts/initial_prompt_a')

        # get the list of dialogues, which will be our experiments
        dialogues = self.load_json('resources/dialogues.json')
        game_ids_select = random.sample(list(dialogues.keys()), N_INSTANCES)

        for exp_index, game_id in enumerate(game_ids_select):
            # create an experiment (for us, named after a topic)
            experiment = self.add_experiment(exp_index)
            # build N_INSTANCES instances for each experiment
            # create a game instance, using a game_id counter/index
            instance = self.add_game_instance(experiment, exp_index)
            # populate the game instance with its parameters
            instance['dialogue'] = dialogues[game_id]
            instance["n_turns"] = len(dialogues[game_id])
            instance['prompt'] = prompt_a
            instance['game_id'] = exp_index

if __name__ == '__main__':
    #random.seed(SEED)
    # always call this, which will actually generate and save the JSON file
    MinecraftGameInstanceGenerator().generate()