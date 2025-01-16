import copy
import random
import string
from typing import List, Dict, Tuple

from clemgame.clemgame import GameInstanceGenerator
from clemgame import file_utils
from games.dmsystem_llm_monolithic.domaindbreader import DomainDBReader

# set the name of the game in the script, as you named the directory
# this name will be used everywhere, including in the table of results
GAME_NAME = "dmsystem_monolithic_llm"
# we will create 10 instances for each experiment; vary this as you wish
N_INSTANCES = 1
# if the generation involves randomness, remember to set a random seed
SEED = 123

LANGUAGE = "en"


class DMSystemInstanceGenerator(GameInstanceGenerator):
    def __init__(self, game_name):
        # always do this to initialise GameInstanceGenerator
        super().__init__(game_name)
        self.game_name = game_name

    def _preparedata(self, taskdetails, domains):
        # filter the tasks based on the domains required
        filteredtasks = {domain.lower(): [] for domain in domains}
        for dialogue in taskdetails.get("single", {}):
            data = taskdetails["single"][dialogue]
            for domain in domains:
                domain_lower = domain.lower()
                if domain_lower in data["domain"]:
                    filteredtasks[domain_lower].append(data)
        return {k: v for k, v in filteredtasks.items() if v}

    def _get_cat_noncat_slots(self, domain, domain_schema, game_slots):
        cat_slots = []
        noncat_slots = []

        for entry in domain_schema:
            if entry["service_name"] == domain:
                for slot in entry["slots"]:
                    slot_name = slot["name"].split("-")[1].strip()
                    if slot["is_categorical"] and slot_name in game_slots:
                        cat_slots.append(slot_name)
                    else:
                        noncat_slots.append(slot_name)

        return cat_slots, noncat_slots

    def _fill_player_prompts(
        self, game_name, game_id, gamedata, domain, taskdlgs, promptsdict, prompt_slots
    ):
        prompt_types = [
            "prompt_a",
            "turn_prompt_a",
            "prompt_b",
            "turn_prompt_b",
            "dbquery_prompt_b",
            "validbooking_prompt_b",
        ]

        for prompt_type in prompt_types:
            gamedata[prompt_type] = self.create_prompt(
                domain,
                taskdlgs[game_id]["goal"],
                gamedata["slots"],
                promptsdict[prompt_type],
            )

        if game_name == "dmsystem_modular_llm":
            gamedata["turn_ss_prompt_b"] = promptsdict["turn_ss_prompt_b"]
            modular_prompt_types = [
                "intent_detection",
                "slot_extraction",
                "followup_generation",
                "booking_aggregator",
            ]
            for prompt_type in modular_prompt_types:
                gamedata[prompt_type] = self.create_prompt(
                    domain,
                    taskdlgs[game_id]["goal"],
                    prompt_slots,
                    promptsdict[prompt_type],
                )

    def _preparegamedata(
        self,
        game_name,
        game_id,
        similarity,
        liberal_processing,
        statusmsg,
        domain,
        domain_schema,
        taskdlgs,
        promptsdict,
    ):
        gamedata = {}
        gamedata["n_turns"] = taskdlgs[game_id]["n_turns"]
        gamedata["similarity"] = similarity
        gamedata["liberal_processing"] = liberal_processing
        gamedata["statusmsg"] = statusmsg
        gamedata["domain"] = domain
        #without games/ prefix in the path, the sqlite connection fails
        gamedata[
            "domaindb_path"
        ] = f"games/{GAME_NAME}/resources/domains/{LANGUAGE}/{domain}-dbase.db"
        gamedata["domain_schema"] = self._normalize_domain_schema(domain, domain_schema)

        gamedata["goal"] = taskdlgs[game_id]["goal"]

        prompt_slots = list(taskdlgs[game_id]["slots"].keys())
        prompt_slots = [slot.split("-")[1].strip() for slot in prompt_slots]
        gamedata["slots"] = {
            new_key: " ".join(value).strip()
            for new_key, (_, value) in zip(
                prompt_slots, taskdlgs[game_id]["slots"].items()
            )
        }

        gamedata["slots"] = {
            key: value
            for key, value in gamedata["slots"].items()
            if value != "dontcare"
        }
        prompt_slots = list(gamedata["slots"].keys())

        gamedata["cat_slots"], gamedata["noncat_slots"] = self._get_cat_noncat_slots(
            domain, domain_schema, gamedata["slots"]
        )
        gamedata["game_name"] = game_name

        self._fill_player_prompts(
            game_name, game_id, gamedata, domain, taskdlgs, promptsdict, prompt_slots
        )

        return gamedata

    def _get_player_prompts(self, game_name):
        prompt_file_names = [
            "initial_prompt_a",
            "turn_prompt_a",
            "initial_prompt_b",
            "turn_prompt_b",
            "dbquery_prompt_b",
            "validbooking_prompt_b"
        ]

        prompts_dict_match_keys = {
            "initial_prompt_a": "prompt_a",
            "turn_prompt_a": "turn_prompt_a",
            "initial_prompt_b": "prompt_b",
            "turn_prompt_b": "turn_prompt_b",
            "dbquery_prompt_b": "dbquery_prompt_b",
            "validbooking_prompt_b": "validbooking_prompt_b"
        }

        promptsdict = {
            prompts_dict_match_keys[file_name]: file_utils.load_template(
                f"resources/initial_prompts/{LANGUAGE}/{file_name}", GAME_NAME
            )
            for file_name in prompt_file_names
        }

        if game_name == "dmsystem_modular_llm":
            additional_prompts = {
                "turn_subsystem_prompt_b": "turn_ss_prompt_b",
                "initial_prompt_intent_detection": "intent_detection",
                "initial_prompt_slot_extraction": "slot_extraction",
                "initial_prompt_followup_generation": "followup_generation",
                "initial_prompt_booking_aggregator": "booking_aggregator",
            }

            promptsdict.update(
                {
                    value: file_utils.load_template(
                        f"resources/initial_prompts/{LANGUAGE}/{key}", game_name
                    )
                    for key, value in additional_prompts.items()
                }
            )

        return promptsdict
    
    def _normalize_domain_schema(self, domain, domain_schema):
        normalized_schema = {}
        for entry in domain_schema:
            if entry["service_name"] != domain:
                continue
            normalized_entry = copy.deepcopy(entry)
            normalized_entry["slots"] = [
                {
                    "name": slot["name"].split("-")[1].strip(),
                    "is_categorical": slot["is_categorical"],
                    "possible_values": slot["possible_values"] if "possible_values" in slot else [],
                }
                for slot in entry["slots"]
            ]
            normalized_schema[entry["service_name"]] = normalized_entry
        return normalized_schema

    def _loaddata(self):
        domain_path = f"resources/domains/{LANGUAGE}"

        domains = (
            file_utils.load_file(f"{domain_path}/topics.txt", GAME_NAME)
            .strip()
            .split("\n")
        )
        domain_schema = file_utils.load_json(f"{domain_path}/schema.json", GAME_NAME)
        promptsdict = self._get_player_prompts(self.game_name)
        gameconfig = file_utils.load_json(
            f"resources/config/{LANGUAGE}/taskconfig.json", self.game_name
        )
        taskdetails = file_utils.load_json(
            f"resources/tasks/{LANGUAGE}/taskdetails.json", GAME_NAME
        )

        return domains, domain_schema, promptsdict, gameconfig, taskdetails

    # define on_generate, a mandatory method
    def on_generate(self):
        num_instances = 0
        domains, domain_schema, promptsdict, gameconfig, taskdetails = self._loaddata()
        filteredtasks = self._preparedata(taskdetails, domains)

        # building the file, one experiment at a time
        for domain in domains:
            domain = domain.lower()
            if domain not in filteredtasks:
                continue
            # create an experiment (for us, named after a topic)

            taskdlgs = random.choices(filteredtasks[domain], k=N_INSTANCES)
            gameinstances = []
            # build N_INSTANCES instances for each experiment
            for game_id in range(N_INSTANCES):
                # set the parameters
                similarity = gameconfig["similarity"]
                statusmsg = gameconfig["statusmsg"]
                liberal_processing = gameconfig["sub-system-liberal"]

                # populate the game instance with its parameters
                data_instance = self._preparegamedata(
                    self.game_name,
                    game_id,
                    similarity,
                    liberal_processing,
                    statusmsg,
                    domain,
                    domain_schema,
                    taskdlgs,
                    promptsdict,
                )
                if data_instance is None:
                    continue

                gameinstances.append(data_instance)

            # create an experiment (for us, named after a topic)
            experiment = self.add_experiment(domain)
            for game_id, gameinst in enumerate(gameinstances):
                # create a game instance, using a game_id counter/index
                instance = self.add_game_instance(experiment, game_id)
                instance["data"] = gameinst
            num_instances += len(gameinstances)

        print(
            f"Generated instances for -{self.game_name} game - {num_instances} instances."
        )

    # an additional method, specific for our example
    def create_prompt(self, topic: str, goal: str, slots: List, prompt: str) -> str:
        """Replace a prompt template with slot values."""
        text = string.Template(prompt).substitute(topic=topic, goal=goal, slots=slots)
        return text


if __name__ == "__main__":
    random.seed(SEED)
    # always call this, which will actually generate and save the JSON file
    DMSystemInstanceGenerator(GAME_NAME).generate()
