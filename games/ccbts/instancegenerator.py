import random
import string

from clemgame.clemgame import GameInstanceGenerator

from games.ccbts.utils.sampleformatter import get_incontext_samples

# set the name of the game in the script, as you named the directory
# this name will be used everywhere, including in the table of results
GAME_NAME = "ccbts"
# we will create 10 instances for each experiment; vary this as you wish
N_INSTANCES = 1
# if the generation involves randomness, remember to set a random seed
SEED = "42"


class CCBTSInstanceGenerator(GameInstanceGenerator):
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
        for board in tests["boards"]:
            for board_object in tests[board]["objects"]:
                for variant in tests[board][board_object]["variants"]:
                    # create an experiment (for us, named after a topic)
                    experiment = self.add_experiment(f"{board}_{board_object}_{variant}")

                    self.train_samples = self.load_json(
                        f'resources/{tests[board][board_object][variant]["TRAIN_DATA_FILE_NAME"]}'
                    )
                    test_samples = self.load_json(
                        f'resources/{tests[board][board_object][variant]["TEST_DATA_FILE_NAME"]}'
                    )

                    if variant == "multi_turn":
                        prompt = self.load_template("resources/initial_prompts/initial_prompt_multiturn")
                    elif variant in ["single_turn", "single_turn_sc", "single_turn_hai", "single_turn_hai_sc", "single_turn_mg"]:
                        prompt = self.load_template("resources/initial_prompts/initial_prompt_singleturn")
                    elif variant in ["regular", "regular_hai", "regular_mg"]:
                        prompt = self.load_template("resources/initial_prompts/initial_prompt_regular")                        

                    incontext_labels = {"INSTRUCTION_LABEL": tests[board][board_object][variant]["fill_labels"]["INSTRUCTION_LABEL"],
                                        "OUTPUT_LABEL": tests[board][board_object][variant]["fill_labels"]["OUTPUT_LABEL"],
                                        "OUTPUT_LABEL_HORDER": tests[board][board_object][variant]["fill_labels"]["OUTPUT_LABEL_HORDER"],
                                        "OUTPUT_LABEL_HORDER_USAGE": tests[board][board_object][variant]["fill_labels"]["OUTPUT_LABEL_HORDER_USAGE"]}

                    #test_samples_combos = random.sample(list(test_samples.keys()), N_INSTANCES)

                    for board_type, objs_type in test_samples.items():
                        for obj, num_shapes in objs_type.items():
                            for total_shapes, combo_names in num_shapes.items():
                                for combo_name in num_shapes[total_shapes]:
                                    #samples_test = random.sample(test_samples[total_shapes][combo_name], 1)
                                    for sample in num_shapes[total_shapes][combo_name]:
                                    #for sample in samples_test:
                                        test_dialogues = sample["dialogues"][variant]["instructions"]
                                        n_turns = len(test_dialogues)
                                        seed_template_name = sample["seed_template"]
                                            
                                        if SEED == "static":
                                            incontext_samples = self.load_file(f'resources/{tests[board][board_object][variant]["STATIC_INCONTEXT_SAMPLES"]}')
                                        else:
                                            incontext_samples = get_incontext_samples(
                                                        board,
                                                        board_object,
                                                        variant,
                                                        tests[board][board_object][variant]["NUM_INCONTEXT_SAMPLES"],
                                                        total_shapes,
                                                        combo_name,
                                                        self.train_samples,
                                                        incontext_labels,
                                                        seed_template_name,
                                                        SEED                                    
                                                    )

                                        # set the parameters
                                        # create a game instance, using a game_id counter/index
                                        instance = self.add_game_instance(experiment, game_id)

                                        # populate the game instance with its parameters
                                        instance["n_turns"] = n_turns
                                        instance["dialogues"] = test_dialogues                          
                                        if variant == "multi_turn":
                                            instance["output_labels"] = {
                                                "output": tests[board][board_object][variant]["fill_labels"][
                                                    "OUTPUT_LABEL"
                                                ],
                                                "function": None,
                                                "usage": None,
                                            }

                                        elif variant in ["single_turn", "single_turn_sc", "single_turn_hai", "single_turn_hai_sc", "single_turn_mg"]:
                                            instance["output_labels"] = {
                                                "output": None,
                                                "function": tests[board][board_object][variant][
                                                    "fill_labels"
                                                ]["OUTPUT_LABEL_HORDER"],
                                                "usage": tests[board][board_object][variant]["fill_labels"][
                                                    "OUTPUT_LABEL_HORDER_USAGE"
                                                ],
                                            }
                                        elif variant in ["regular", "regular_hai", "regular_mg"]:
                                            instance["output_labels"] = {
                                                "output": tests[board][board_object][variant]["fill_labels"][
                                                    "OUTPUT_LABEL"
                                                ],
                                                "function": None,
                                                "usage": None,
                                            }

                                        if incontext_samples:
                                            tests[board][board_object][variant]["fill_labels"][
                                                "INCONTEXT_SAMPLES"
                                            ] = incontext_samples
                                        else:
                                            tests[board][board_object][variant]["fill_labels"][
                                                "INCONTEXT_SAMPLES"
                                            ] = ""

                                        tests[board][board_object][variant]["fill_labels"][
                                            "COMBO_NAME"
                                        ] = combo_name
                                        tests[board][board_object][variant]["fill_labels"]["COLORS"] = sample["colors"]

                                        instance["prompt"] = self.create_prompt(
                                            prompt,
                                            **tests[board][board_object][variant]["fill_labels"],
                                        )
                                        instance["rows"] = tests["board"]["rows"]
                                        instance["cols"] = tests["board"]["cols"]
                                        instance["test_variant"] = variant
                                        game_id += 1
        print(f"Generated instances for CCBTS game - {game_id - 1} instances.")

    # an additional method, specific for our example
    def create_prompt(self, prompt: str, **kwargs) -> str:
        """Replace a prompt template with slot values."""
        text = string.Template(prompt).safe_substitute(**kwargs)

        return text


if __name__ == "__main__":
    #random.seed(SEED)
    # always call this, which will actually generate and save the JSON file
    CCBTSInstanceGenerator().generate()
