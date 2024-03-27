import random
import string

from clemgame.clemgame import GameInstanceGenerator

from games.ccbts.utils.sampleformatter import get_incontext_samples

# set the name of the game in the script, as you named the directory
# this name will be used everywhere, including in the table of results
GAME_NAME = "ccbts_human"
# we will create 10 instances for each experiment; vary this as you wish
N_INSTANCES = 1
#Number of turns in human play
N_TURNS = 3
# if the generation involves randomness, remember to set a random seed
SEED = "static"


class CCBTSHumanInstanceGenerator(GameInstanceGenerator):
    def __init__(self):
        # always do this to initialise GameInstanceGenerator
        super().__init__(GAME_NAME)   

    # define on_generate, a mandatory method
    def on_generate(self):
        # get the list of topics, which will be our experiments
        tests = self.load_json("resources/tests.json")
        # get the prompts for player a and player b
        # we'll keep the prompts fixed in all instances, replacing only the
        # necessary slots (but you can do it differently)

        game_id = 1
        for level in tests["levels"]:
            variants = tests[level]["variants"]
            for subtest in variants:
                # create an experiment (for us, named after a topic)
                experiment = self.add_experiment(f"{level}_{subtest}")

                self.train_samples = self.load_json(
                    f'resources/{tests[level][subtest]["TRAIN_DATA_FILE_NAME"]}'
                )
                '''
                test_samples = self.load_json(
                    f'resources/{tests[level][subtest]["TEST_DATA_FILE_NAME"]}'
                )
                '''

                if subtest == "forder":
                    prompt = self.load_template("resources/initial_prompts/initial_prompt_atomic")
                elif subtest == "horder":
                    prompt = self.load_template("resources/initial_prompts/initial_prompt_compound")

                incontext_labels = {"INSTRUCTION_LABEL": tests[level][subtest]["fill_labels"]["INSTRUCTION_LABEL"],
                                    "OUTPUT_LABEL": tests[level][subtest]["fill_labels"]["OUTPUT_LABEL"],
                                    "OUTPUT_LABEL_HORDER": tests[level][subtest]["fill_labels"]["OUTPUT_LABEL_HORDER"],
                                    "OUTPUT_LABEL_HORDER_USAGE": tests[level][subtest]["fill_labels"]["OUTPUT_LABEL_HORDER_USAGE"]}

                for index in range(N_INSTANCES):
                    incontext_samples = self.load_file(f'resources/{tests[level][subtest]["STATIC_INCONTEXT_SAMPLES"]}')
                    instance = self.add_game_instance(experiment, game_id)

                    # populate the game instance with its parameters
                    instance["n_turns"] = N_TURNS
                    #instance["dialogues"] = test_dialogues                          
                    if subtest == "forder":
                        instance["output_labels"] = {
                            "output": tests[level][subtest]["fill_labels"][
                                "OUTPUT_LABEL"
                            ],
                            "function": None,
                            "usage": None,
                        }

                    elif subtest == "horder":
                        instance["output_labels"] = {
                            "output": None,
                            "function": tests[level][subtest][
                                "fill_labels"
                            ]["OUTPUT_LABEL_HORDER"],
                            "usage": tests[level][subtest]["fill_labels"][
                                "OUTPUT_LABEL_HORDER_USAGE"
                            ],
                        }
                    tests[level][subtest]["fill_labels"][
                                "INCONTEXT_SAMPLES"
                            ] = incontext_samples

                    instance["prompt"] = self.create_prompt(
                        prompt,
                        **tests[level][subtest]["fill_labels"],
                    )
                    instance["rows"] = tests["board"]["rows"]
                    instance["cols"] = tests["board"]["cols"]
                    game_id += 1

                '''
                for shape, colors in test_samples.items():
                    for color, locations in colors.items():
                        for location, dialogues in locations.items():
                            if isinstance(dialogues[0], list):
                                test_instruction = dialogues[0][0]["<Programmer>"]
                                test_dialogues = dialogues[0]
                                n_turns = len(dialogues[0])
                            else:
                                test_instruction = dialogues[0]["<Programmer>"]
                                test_dialogues = [dialogues[0]]
                                n_turns = 1
                            
                            if SEED == "static":
                                incontext_samples = self.load_file(f'resources/{tests[level][subtest]["STATIC_INCONTEXT_SAMPLES"]}')
                            else:
                                incontext_samples = get_incontext_samples(
                                            level,
                                            subtest,
                                            tests[level][subtest]["NUM_INCONTEXT_SAMPLES"],
                                            tests[level]["matching_combos"][shape],
                                            shape,
                                            color,
                                            location,
                                            self.train_samples,
                                            incontext_labels,
                                            SEED                                    
                                        )
                            test_instruction = ("\nInstruction\n" + test_instruction)
                            # set the parameters
                            # create a game instance, using a game_id counter/index
                            instance = self.add_game_instance(experiment, game_id)

                            # populate the game instance with its parameters
                            instance["n_turns"] = n_turns
                            #instance["dialogues"] = test_dialogues                          
                            if subtest == "forder":
                                instance["output_labels"] = {
                                    "output": tests[level][subtest]["fill_labels"][
                                        "OUTPUT_LABEL"
                                    ],
                                    "function": None,
                                    "usage": None,
                                }

                            elif subtest == "horder":
                                instance["output_labels"] = {
                                    "output": None,
                                    "function": tests[level][subtest][
                                        "fill_labels"
                                    ]["OUTPUT_LABEL_HORDER"],
                                    "usage": tests[level][subtest]["fill_labels"][
                                        "OUTPUT_LABEL_HORDER_USAGE"
                                    ],
                                }

                            tests[level][subtest]["fill_labels"][
                                "INCONTEXT_SAMPLES"
                            ] = incontext_samples

                            instance["prompt"] = self.create_prompt(
                                prompt,
                                **tests[level][subtest]["fill_labels"],
                            )
                            instance["rows"] = tests["board"]["rows"]
                            instance["cols"] = tests["board"]["cols"]
                            game_id += 1
                '''

    # an additional method, specific for our example
    def create_prompt(self, prompt: str, **kwargs) -> str:
        """Replace a prompt template with slot values."""
        text = string.Template(prompt).safe_substitute(**kwargs)

        return text


if __name__ == "__main__":
    #random.seed(SEED)
    # always call this, which will actually generate and save the JSON file
    CCBTSHumanInstanceGenerator().generate()
