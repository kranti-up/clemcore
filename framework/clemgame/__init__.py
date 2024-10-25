import abc
import collections
import copy
import json
import os.path
import sys
from datetime import datetime
from typing import List, Dict, Tuple, Any
from tqdm import tqdm
from dataclasses import dataclass
from types import SimpleNamespace
import importlib
import importlib.util
import inspect
import logging

import framework.backends as backends
import framework.utils.file_utils as file_utils
import framework.utils.transcript_utils as transcript_utils
import framework.clemgame.metrics as ms

logger = logging.getLogger(__name__)
stdout_logger = logging.getLogger("framework.run")

game_registry = []  # list of game specs to load from dynamically


@dataclass(frozen=True)
class GameSpec(SimpleNamespace):
    """Base class for game specifications.
    Holds all necessary information to play game in clembench (see README for list of attributes)
    """

    def __init__(self, **kwargs):
        # JJ: explicit args for 'required fields' would be better
        super().__init__(**kwargs)
        # check for required fields
        if "game_name" not in self:
            raise KeyError(f"No game name specified in entry {kwargs}")
        if "game_path" not in self:
            raise KeyError(f"No game path specified in {kwargs}")

    def __repr__(self) -> str:
        """Returns string representation of this GameSpec."""
        return f"GameSpec({str(self)})"

    def __str__(self) -> str:
        """Returns GameSpec instance attribute dict as string."""
        return str(self.__dict__)

    def __getitem__(self, item: str):
        """Access GameSpec instance attributes like dict items.
        Args:
            item: The string name of the instance attribute to get.
        Returns:
            The value of the GameSpec instance attribute, or if the instance does not have the attribute, the string
            passed as argument to this method.
        """
        return getattr(self, item)

    def __contains__(self, attribute) -> bool:
        """Check GameSpec instance attributes like dict keys.
        Args:
            attribute: The string name of the instance attribute to check for.
        Returns:
            True if the GameSpec instance contains an attribute with the passed string name, False otherwise.
        """
        return hasattr(self, attribute)

    @classmethod
    def from_dict(cls, spec: Dict):
        """Initialize a GameSpec from a dictionary.
        Can be used to directly create a GameSpec from a game registry entry.
        Args:
            spec: A game-specifying dict.
        Returns:
            A GameSpec instance with the data specified by the passed dict.
        """
        return cls(**spec)

    def matches(self, spec: Dict) -> bool:
        """Check if the game features match a given specification.
        Args:
            spec: A game-specifying dict.
        Returns:
            True if the game features match the passed specification, False otherwise.
        Raises:
            KeyError: The GameSpec instance does not contain an attribute corresponding to a key in the passed
                game-specifying dict.
        """
        for key, value in spec.items():
            if not self.__contains__(key):
                raise KeyError(f"The specified key '{key}' for selecting games is not set in the game registry "
                               f"for game '{self['game_name']}'")
            if type(self[key]) == str:
                if not self[key] == value:
                    return False
            elif type(self[key]) == list:
                if value not in self[key]:
                    return False
        return True

    def get_game_file(self) -> str:
        """Get the file path of the master.py of the game specified by this GameSpec instance.
        Returns:
            The file path of the master.py of the game specified by this GameSpec instance as a string.
        """
        if os.path.isabs(self.game_path):
            return os.path.join(self.game_path, "master.py")
        else:
            return os.path.join(file_utils.project_root(), self.game_path, "master.py")

    def game_file_exists(self) -> bool:
        """Check if master.py can be located at the specified game_path.
        Returns:
            True if the master.py is located at the specified game_path, False otherwise.
        """
        return True if os.path.isfile(self.get_game_file()) else False


def load_custom_game_registry(_game_registry_path: str = None, is_optional=True):
    """Load a custom game registry.
    Handled as module-level variable.
    Args:
        _game_registry_path: The path to a custom game registry JSON file. Optional: If not passed, default path is
            used.
        is_optional: TODO: what is this supposed to do here?
    """
    # optional custom registry loaded first, so that these entries come first in the game registry list
    if not _game_registry_path:
        _game_registry_path = os.path.join(file_utils.project_root(), "clemgame", "game_registry_custom.json")
    load_game_registry(_game_registry_path, is_mandatory=not is_optional)


def load_game_registry(_game_registry_path: str = None, is_mandatory=True):
    """Load the game registry.
    Handled as module-level variable.
    Args:
        _game_registry_path: The path to the game registry JSON file. Optional: If not passed, default path is used.
        is_mandatory: If True, a FileNotFoundError is raised if the game registry JSON file does not exist at the
            path specified in _game_registry_path (or the default path, if nothing is passed to _game_registry_path).
    Raises:
        FileNotFoundError: If True is passed to is_mandatory, FileNotFoundError is raised if the game registry JSON file
            does not exist at the path specified in _game_registry_path (or the default path, if nothing is passed to
            _game_registry_path).
    """
    if not _game_registry_path:
        _game_registry_path = os.path.join(file_utils.project_root(), "clemgame", "game_registry.json")
    if not os.path.isfile(_game_registry_path):
        if is_mandatory:
            raise FileNotFoundError(f"The file game registry at '{_game_registry_path}' does not exist. "
                                    f"Create game registry as a game_registry.json file and try again.")
        else:
            return  # do nothing
    with open(_game_registry_path, encoding='utf-8') as gr:
        _game_listing = json.load(gr)
        for _game_entry in _game_listing:
            _game_spec: GameSpec = GameSpec.from_dict(_game_entry)
            if _game_spec.game_file_exists():
                game_registry.append(_game_spec)
            else:
                stdout_logger.warning(
                    f"Game master for {_game_spec.game_name} not found in '{_game_spec['game_path']}'. "
                    f"Game '{_game_spec.game_name}' not added to available games. "
                    f"Update game_registry.json (or game_registry_custom.json) with the right path to include it."
                )


def select_game(game_name: str) -> GameSpec:
    """Select a GameSpec from the game registry by game name.
    Args:
        game_name: String name of the selected game.
    Returns:
        A GameSpec instance from the game registry corresponding to the passed game_name.
    Raises:
        ValueError: No game specification matching the passed game_name was found in the game registry.
    """
    # return first entry that matches game_name
    for game in game_registry:
        if game["game_name"] == game_name:
            return game
    raise ValueError(
        f"No games found matching the given specification '{game_name}'. "
        "Make sure the game name matches the value in game_registry.json")
    # extension to select subset of games
    # (postponed because it introduces more complexity
    # on things like how to specify specific episodes,
    # and thus can be easier done by looping over an
    # explicit list of games with a bash script (see clembench/scripts/run_benchmark.sh)

    # select relevant games from game registry
    # selected_games = []
    # properties = {}
    # is_single_game = True
    # if game_name.endswith(".json"):
    #     is_single_game = False
    #     with open(os.path.join(file_utils.project_root(), game_name)) as f:
    #         properties = json.load(f)
    #     # add default values
    #     if "lang" not in properties:
    #         properties["language"] = "en"
    #     if "image" not in properties:
    #         properties["image"] = "none"
    #     # examples:
    #     # {"benchmark" : "2.0"} # run all English textual games marked for benchmark version 2.0
    #     # {"benchmark" : "1.5", "lang": "ru"} # run all games of benchmark version 1.5 for which Russian versions exist
    #     # {"main_game": "matchit"} # to run all English textual matchit game versions
    #     # {"image": "single", "main_game": "matchit"} # to run all English multimodal matchit game versions
    #
    # if is_single_game:
    #     # return first entry that matches game_name
    #     for game in game_registry:
    #         if game["game_name"] == game_name:
    #             return game
    # else:
    #     for game in game_registry:
    #         if game.matches(properties):
    #             selected_games.append(game)
    #
    # if len(selected_games) == 0:
    #     raise ValueError(f"No games found matching the given specification '{game_name}'. "
    #                      "Make sure game name or attribute names and values match game_registry.json")
    # return selected_games


class Player(abc.ABC):
    """A participant of a game.
    A player can respond via a custom implementation, human input or a language model:
    - the programmatic players are called via the _custom_response() method
    - the human players are called via the _terminal_response() method
    - the backend players are called via the generate_response() method of the backend
    """

    def __init__(self, model: backends.Model):
        """
        Args:
            model: A backends.Model instance to be used by this Player instance.
        """
        self.model = model
        self.descriptor: str = None
        logger.info("Player %s", self.get_description())

    def get_description(self) -> str:
        """Get a description string for this Player instance.
        Returns:
            A string describing this Player instance's class name and used model.
        """
        return f"{self.__class__.__name__}, {self.model}"

    def __call__(self, messages: List[Dict], turn_idx) -> Tuple[Any, Any, str]:
        """Get a response from this Player instance's model.
        Passes a messages list and turn index to the model, creates a response dict for record logging, including
        timestamps and call duration, and returns a Player response tuple.
        Args:
            messages: A list of message dicts, containing the current conversation history to prompt the model with.
            turn_idx: The current turn index.
        Returns:
            A Player response tuple consisting of: The prompt as converted by the model backend; the full response dict
            to be used for recording/logging; the response text produced by the model, as post-processed by the model
            backend.
        """
        call_start = datetime.now()
        prompt = messages
        response = dict()
        if isinstance(self.model, backends.CustomResponseModel):
            response_text = self._custom_response(messages, turn_idx)
        elif isinstance(self.model, backends.HumanModel):
            response_text = self._terminal_response(messages, turn_idx)
        else:
            prompt, response, response_text = self.model.generate_response(messages)
        call_duration = datetime.now() - call_start
        response["clem_player"] = {
            "call_start": str(call_start),
            "call_duration": str(call_duration),
            "response": response_text,
            "model_name": self.model.get_name()
        }
        return prompt, response, response_text

    def _terminal_response(self, messages, turn_idx) -> str:
        """Response for human interaction via terminal.
        Overwrite this method to customize human inputs (model_name: human, terminal).
        Args:
            messages: A list of dicts that contain the history of the conversation.
            turn_idx: The index of the current turn.
        Returns:
            The human response as text.
        """
        latest_response = "Nothing has been said yet."
        if messages:
            latest_response = messages[-1]["content"]
        print(f"\n{latest_response}")
        user_input = input(f"Your response as {self.__class__.__name__} (turn: {turn_idx}):\n")
        return user_input

    def _custom_response(self, messages, turn_idx) -> str:
        """Response for programmatic Player interaction.
        Overwrite this method to implement programmatic behavior (model_name: mock, dry_run, programmatic, custom).
        Args:
            messages: A list of dicts that contain the history of the conversation.
            turn_idx: The index of the current turn.
        Returns:
            The programmatic response as text.
        """
        raise NotImplementedError()


class GameResourceLocator(abc.ABC):
    """Provides access to game specific resources.
    Note: You should access game-specific resources only via the game resource locator! The locator knows how to refer
    to them.

    For example use: `gm.load_json("my_file")` which is located directly at your game directory `game/my_file.json`.

    You can access subdirectories by giving `gm.load_json("sub/my_file")` in `game/sub/my_file.json`.
    """

    def __init__(self, name: str):
        """
        Args:
            name: The name of the game.
        """
        self.name = name
        self.logger = logging.getLogger(self.__class__.__module__)

    def file_path(self, file_name: str) -> str:
        """Get the absolute path to a game resource file.
        Sometimes we only need the path to a file, but not to load it.
        Args:
            file_name: The name of the game resource file. Can be a sub-path.
        Returns:
            The absolute path to the file in the game directory as string.
        """
        return file_utils.file_path(file_name, self.name)

    def load_instances(self, game_path, instances_name) -> dict:
        """Construct instances path and return json object of the instance file.
        Args:
            game_path: Path to the game directory.
            instances_name: Name of the instances JSON file.
        Returns:
            A dict containing the contents of the given instances file.
        """
        if instances_name is None:
            instances_name = "instances"
        if not instances_name.endswith(".json"):
            instances_name += ".json"
        #TODO: currently, this requires game path to be relative to clembench, this needs some further refinement
        # to also allow for absolute paths
        # i.e., by being set from the game registry either in the GameResourceLocator or in the GameBenchmark
        fp = os.path.join(file_utils.project_root(), game_path, "in", instances_name)
        with open(fp, encoding='utf8') as f:
            instances = json.load(f)
        return instances

    def load_template(self, file_name: str) -> str:
        """Load a .template file from the game directory.
        Args:
            file_name: The name of the template file. Can have subdirectories e.g. "sub/my_file".
        Returns:
            The template file content as string.
        """
        return file_utils.load_template(file_name, self.name)

    def load_json(self, file_name: str) -> Dict:
        """Load a .json file from the game (or game results) directory.
        Args:
            file_name: The name of the JSON file. Can have subdirectories e.g. "sub/my_file".
        Returns:
            The JSON file content as dict.
        """
        return file_utils.load_json(file_name, self.name)

    def load_results_json(self, file_name: str, results_dir: str, dialogue_pair: str) -> Dict:
        """Load a .json file from your game results directory.
        Args:
            file_name: The name of the JSON file. Can have subdirectories e.g. "sub/my_file".
            results_dir: The string path to the results directory.
            dialogue_pair: The pair of models that produced the results. TODO: Check if this is still viable currently
        Returns:
            The JSON file content as dict.
        """
        return file_utils.load_results_json(file_name, results_dir, dialogue_pair, self.name)

    def load_csv(self, file_name: str) -> Dict:
        """Load a .csv file from your game directory.
        Args:
            file_name: The name of the CSV file. Can have subdirectories e.g. "sub/my_file".
        Returns:
            The CSV file content as dict.
        """
        return file_utils.load_csv(file_name, self.name)

    def load_file(self, file_name: str, file_ending: str = None) -> str:
        """Load an arbitrary file from your game directory.
        Args:
            file_name: The name of the file. Can have subdirectories e.g. "sub/my_file".
            file_ending: The file type suffix of the file. Optional: Can be part of file_name.
        Returns:
            The file content as string.
        """
        return file_utils.load_file(file_name, self.name, file_ending=file_ending)

    def store_file(self, data, file_name: str, sub_dir: str = None):
        """Store a file in your game directory. The top-level directory is 'games'.
        Args:
            data: The data to store in the file.
            file_name: The name of the file. Can have subdirectories e.g. "sub/my_file".
            sub_dir: The subdirectory to store the file in. Automatically created when given; otherwise an error will
                be thrown. TODO: Check how this actually works, since old docstring is unclear
        """
        fp = file_utils.store_game_file(data, file_name, self.name, sub_dir=sub_dir)
        self.logger.info("Game file stored to %s", fp)

    def store_results_file(self, data, file_name: str, dialogue_pair: str, sub_dir: str = None, root_dir: str = None):
        """Store a results file in your game results' directory. The top-level directory is 'results'.
        Args:
            data: The data to store in the file.
            file_name: The name of the file. Can have subdirectories e.g. "sub/my_file".
            dialogue_pair: The pair of models that produced the results. TODO: Check if this is still viable currently
            sub_dir: The subdirectory to store the results file in. Automatically created when given; otherwise an
                error will be thrown. TODO: Check how this actually works, since old docstring is unclear
            root_dir: An alternative results directory structure given as a relative or absolute path.
        """
        fp = file_utils.store_game_results_file(data, file_name, dialogue_pair, self.name,
                                                sub_dir=sub_dir, root_dir=root_dir)
        self.logger.info("Results file stored to %s", fp)

    def results_path_for(self, results_dir: str, dialogue_pair: str):
        """
        TODO: Check what this actually does
        """
        return file_utils.game_results_dir_for(results_dir, dialogue_pair, self.name)


class GameRecorder(GameResourceLocator):
    """Base class for benchmark record keeping and logging."""
    def __init__(self, name: str):
        """
        Args:
            name: The name of the game.
        """
        super().__init__(name)
        self.log_current_turn = -1
        self.interactions = {  # Stores players and turn during the runs
            "players": {},
            "turns": []
        }
        self.requests = []  # Stores calls to the API

    def log_next_turn(self):
        """Call this method to group interactions per turn."""
        self.log_current_turn += 1
        self.interactions["turns"].append([])

    def log_key(self, key: str, value: Any):
        """Add a key and value to the internal log."""
        self.interactions[key] = value
        self.logger.info(f"{self.name}: Logged a game-specific interaction key: {key}.")

    def log_players(self, players_dic: Dict):
        self.interactions["players"] = players_dic
        self.logger.info(f"{self.name}: Logged players metadata.")

    def log_event(self, from_: str, to: str, action: Dict, call: Tuple[Any, Any] = None):
        """Add an event to the internal log.
        It can be only an action or an action plus an API call that should have the same timestamp as the action.
        Args:
            from_: The identifier string of the Player/GM that made the call.
            to: The identifier string of the Player/GM target of the call. TODO: Check what actually happens here
            action: The benchmark action to be logged.
            call: If given, this is a tuple whose first element is the input prompt object (after API-specific
                manipulation) as passed to the API and the second element is the raw response object as returned by the
                API.
        """
        assert self.log_current_turn >= 0, f"Call log_add_new_turn at least once " \
                                           f"(log_current_turn={self.log_current_turn})"
        timestamp = datetime.now().isoformat()
        action_obj = {
            "from": from_,
            "to": to,
            "timestamp": timestamp,
            "action": action
        }
        self.interactions["turns"][self.log_current_turn].append(copy.deepcopy(action_obj))
        self.logger.info(
            f"{self.name}: Logged {action['type']} action ({from_}->{to}).")
        if call:
            call_obj = {
                "timestamp": timestamp,
                "manipulated_prompt_obj": self._needs_copy(call[0]),
                "raw_response_obj": self._needs_copy(call[1])
            }
            self.requests.append(call_obj)
            self.logger.info(f"{self.name}: Logged a call with timestamp {timestamp}")

    @staticmethod
    def _needs_copy(call_obj):
        """Deepcopy objects that may lead to reference issues.
        Args:
            call_obj: The object to be deep-copied for safety.
        Returns:
            The deep-copy of the passed object, or the original object if it is safe to use.
            TODO: Check how this is used
        """
        if isinstance(call_obj, Dict) or isinstance(call_obj, List):
            return copy.deepcopy(call_obj)
        elif isinstance(call_obj, str):
            return call_obj[:]
        return call_obj

    def store_records(self, results_root: str, dialogue_pair_desc: str, game_record_dir: str):
        """Store benchmark records.
        Raise warnings if a mandatory element is empty or format is wrong.
        Args:
            results_root: The root path to the results directory.
            dialogue_pair_desc: A description of the Player pair.
            game_record_dir: The game's record directory path.
            TODO: Check all arguments and how this is used
        """
        if not self.interactions["players"]:
            self.logger.warning(f"Players metadada is missing!")
        else:
            for name in self.interactions["players"]:
                """The transcript builder relies on specific player identifiers."""
                try:
                    assert name == "GM" or name.startswith("Player ")
                except AssertionError:
                    self.logger.warning(f"Invalid player identifiers, html builder won't work.")
        if not self.interactions["turns"]:
            self.logger.warning(f"Interaction logs are missing!")
        if not self.requests:
            self.logger.warning(f"No calls logged!")
        self.store_results_file(self.interactions, "interactions.json",
                                dialogue_pair_desc,
                                sub_dir=game_record_dir,
                                root_dir=results_root)
        self.store_results_file(self.requests, "requests.json",
                                dialogue_pair_desc,
                                sub_dir=game_record_dir,
                                root_dir=results_root)


class GameMaster(GameRecorder):
    """
    The game master is the master of a specific game. The master
    - prepares a concrete game instance
    - plays an episode of a game instance
    - records a game episode
    - evaluates the game episode records
    - builds the interaction transcripts
    """
    def __init__(self, name: str, experiment: Dict, player_models: List[backends.Model] = None):
        """
        Args:
            name: The name of the game.
            experiment: The experiment (set of instances) to use.
            player_models: Player models to use for one or two players.
        """
        super().__init__(name)
        self.experiment: Dict = experiment
        self.player_models: List[backends.Model] = player_models

    def setup(self, **kwargs):
        """Load resources and prepare everything to play the game.
        Needs to log the players dictionary via self.log_players(players_dict).
        Args:
            kwargs: Keyword arguments used to set up the GameMaster instance. TODO: Check how this is used
        """
        raise NotImplementedError()

    def play(self) -> None:
        """Play the game (multiple turns of a specific game instance)."""
        raise NotImplementedError()


class GameScorer(GameResourceLocator):
    """Calculates scores based on interaction logs."""
    def __init__(self, name: str, experiment: Dict, game_instance: Dict):
        super().__init__(name)
        self.experiment = experiment
        self.game_instance = game_instance
        self.scores = {  # Stores values of score computation
            "turn scores": {},
            "episode scores": {},
        }

    def store_scores(self, results_root: str, dialogue_pair: str, game_record_dir: str):
        self.store_results_file(self.scores, "scores.json",
                                dialogue_pair=dialogue_pair,
                                sub_dir=game_record_dir,
                                root_dir=results_root)

    def log_turn_score(self, turn_idx, score_name, score_value):
        if isinstance(score_value, bool):
            self.logger.warning(f"{self.name}: Score {score_name} value is boolean, this can break the eval!")
        if turn_idx not in self.scores["turn scores"]:
            self.scores["turn scores"][turn_idx] = {}
        if score_name in self.scores["turn scores"][turn_idx]:
            self.logger.warning(f"{self.name}: Score {score_name} overwritten at turn {turn_idx}!")
        self.scores["turn scores"][turn_idx][score_name] = score_value
        self.logger.info(f"{self.name}: Logged turn {turn_idx} score {score_name}={score_value}.")

    def log_episode_score(self, score_name, score_value):
        if score_name in self.scores["episode scores"]:
            self.logger.warning(f"{self.name}: Episode score {score_name} overwritten!")
        self.scores["episode scores"][score_name] = score_value
        self.logger.info(f"{self.name}: Logged episode score {score_name}={score_value}.")

    def compute_scores(self, episode_interactions: Dict) -> None:
        self.score_turns(episode_interactions)
        self.score_game(episode_interactions)

    def score_turns(self, episode_interactions: Dict) -> None:
        # Loop over turns, calculate and log turn-specific scores
        raise NotImplementedError()

    def score_game(self, episode_interactions: Dict) -> None:
        self.score_game_end(episode_interactions)
        self.score_requests(episode_interactions)
        self.log_main_score(episode_interactions)

    def score_game_end(self, episode_interactions: Dict) -> None:
        aborted = int(episode_interactions[ms.METRIC_ABORTED])
        lose = int(episode_interactions[ms.METRIC_LOSE]) if not aborted else 0
        success = 1 - lose if not aborted else 0

        self.log_episode_score(ms.METRIC_ABORTED, aborted)
        self.log_episode_score(ms.METRIC_LOSE, lose)
        self.log_episode_score(ms.METRIC_SUCCESS, success)

    def score_requests(self, episode_interactions: Dict):
        # logging total request count, parsed, violated, and success ratio of parsed requests over all requests
        request_count = episode_interactions[
            ms.METRIC_REQUEST_COUNT]  # could also be calculated by adding parsed and violated requests
        parsed_requests = episode_interactions[ms.METRIC_REQUEST_COUNT_PARSED]
        violated_requests = episode_interactions[ms.METRIC_REQUEST_COUNT_VIOLATED]

        self.log_episode_score(ms.METRIC_REQUEST_COUNT, request_count)
        self.log_episode_score(ms.METRIC_REQUEST_COUNT_PARSED, parsed_requests)
        self.log_episode_score(ms.METRIC_REQUEST_COUNT_VIOLATED, violated_requests)
        self.log_episode_score(ms.METRIC_REQUEST_SUCCESS, parsed_requests / request_count)

    def log_main_score(self, episode_interactions: Dict):
        # Replace this function call with a function that logs your main score aka BENCH_SCORE
        raise NotImplementedError()


class DialogueGameMaster(GameMaster):
    """Extended GameMaster, implementing turns as described in the clembench paper.
    Has most logging and gameplay procedures implemented, including convenient logging methods.
    """
    def __init__(self, name: str, experiment: dict, player_models: List[backends.Model]):
        """
        Args:
            name: The name of the game.
            experiment: The experiment (set of instances) to use.
            player_models: Player models to use for one or two players.
        """
        super().__init__(name, experiment, player_models)
        # the logging works with an internal mapping of "Player N" -> Player
        self.players_by_names: Dict[str, Player] = collections.OrderedDict()
        self.messages_by_names: Dict[str, List] = dict()
        self.current_turn: int = 0

    def get_players(self) -> List[Player]:
        """Get a list of the players."""
        return list(self.players_by_names.values())

    def add_player(self, player: Player):
        """Add a player to the game.
        Note: The players will be called in the same order as added!
        Args:
            player: The player to be added to the game.
        """
        idx = len(self.players_by_names)
        player.descriptor = f"Player {idx + 1}"
        self.players_by_names[player.descriptor] = player
        self.messages_by_names[player.descriptor] = []

    def setup(self, **kwargs):
        """Load resources and prepare everything to play the game.
        Needs to log the players dictionary via self.log_players(players_dict).
        Intended to be left as-is by inheriting classes. Implement additional setup functionality in the _on_setup
        method.
        Args:
            kwargs: Keyword arguments used to set up the GameMaster instance. TODO: Check how this is used
        """
        self._on_setup(**kwargs)
        # log players
        players_descriptions = collections.OrderedDict(GM=f"Game master for {self.name}")
        for name, player in self.players_by_names.items():
            players_descriptions[name] = player.get_description()
        # log player ID and description dict:
        self.log_players(players_descriptions)

    def _on_setup(self, **kwargs):
        """Method executed before default setup method content.
        Template method: must be implemented!
        Use add_player() here to add the players.
        Args:
            kwargs: Keyword arguments of the game instance. TODO: Check what's supposed to be passed here
        """
        raise NotImplementedError()

    def play(self) -> None:
        """Main play loop method.
        This method is called to run the game for benchmarking.
        Intended to be left as-is by inheriting classes. Implement additional setup functionality in the
        _on_before_game, _does_game_proceed, _on_before_turn, _should_reprompt, _on_before_reprompt, _on_after_turn and
        _on_after_game methods.
        """
        self._on_before_game()
        inner_break = False
        while not inner_break and self._does_game_proceed():
            self.log_next_turn()  # not sure if we want to do this always here (or add to _on_before_turn)
            self._on_before_turn(self.current_turn)
            self.logger.info(f"{self.name}: %s turn: %d", self.name, self.current_turn)
            for player in self.__player_sequence():
                if not self._does_game_proceed():
                    inner_break = True  # break outer loop without calling _does_game_proceed again
                    break  # potentially stop in between player turns
                self.prompt(player)
                while self._should_reprompt(player):
                    self._on_before_reprompt(player)
                    self.prompt(player, is_reprompt=True)
            self._on_after_turn(self.current_turn)
            self.current_turn += 1
        self._on_after_game()

    def prompt(self, player: Player, is_reprompt=False):
        """Prompt a player model.
        Args:
            player: The Player instance to be prompted.
            is_reprompt: If this is a reprompt attempt. This is intended for re-prompting with modified prompts.
        """
        # GM -> Player
        history = self.messages_by_names[player.descriptor]
        assert history, f"messages history must not be empty for {player.descriptor}"

        last_entry = history[-1]
        assert last_entry["role"] != "assistant", "Last entry should not be assistant " \
                                                  "b.c. this would be the role of the current player"
        message = last_entry["content"]

        action_type = 'send message' if not is_reprompt else 'send message (reprompt)'
        action = {'type': action_type, 'content': message}
        self.log_event(from_='GM', to=player.descriptor, action=action)

        _prompt, _response, response_message = player(history, self.current_turn)

        # Player -> GM
        action = {'type': 'get message', 'content': response_message}
        # log 'get message' event including backend/API call:
        self.log_event(from_=player.descriptor, to="GM", action=action, call=(_prompt, _response))

        # GM -> GM
        self.__validate_parse_and_add_player_response(player, response_message)

    def _should_reprompt(self, player: Player):
        """Method to check if a Player should be re-prompted.
        This is intended to check for invalid responses.
        Args:
            player: The Player instance to re-prompt.
        """
        return False

    def _on_before_reprompt(self, player: Player):
        """Method executed before reprompt is passed to a Player.
        Hook
        Change the prompt to reprompt the player on e.g. an invalid response.
        Add the new prompt to the players message via self.add_user_message(player, new_prompt)
        Args:
            player: The Player instance that produced the invalid response.
        """
        pass

    def log_message_to(self, player: Player, message: str):
        """            GM -> Player        """
        action = {'type': 'send message', 'content': message}
        self.log_event("GM", player.descriptor, action)

    def log_message_to_self(self, message: str):
        """            GM -> GM        """
        action = {'type': 'metadata', 'content': message}
        self.log_event("GM", "GM", action)

    def log_to_self(self, type_: str, value: str):
        """            GM -> GM        """
        action = {'type': type_, 'content': value}
        self.log_event("GM", "GM", action)

    def add_message(self, player: Player, utterance: str, role: str):
        message = {"role": role, "content": utterance}
        history = self.messages_by_names[player.descriptor]
        history.append(message)

    def add_user_message(self, player: Player, utterance: str):
        self.add_message(player, utterance, role="user")

    def add_assistant_message(self, player: Player, utterance: str):
        self.add_message(player, utterance, role="assistant")

    def __validate_parse_and_add_player_response(self, player: Player, utterance: str):
        # todo: it seems we should change the order here: Parse should come first, and then validate.
        # While parse might throw a parsing (format error) validate would check solely for satisfied game rules.
        # Note: this would allow to cut off too long responses (during parse) and to only validate on the cut off piece.
        if self._validate_player_response(player, utterance):
            utterance = self.__parse_response(player, utterance)
            self.add_assistant_message(player, utterance)
            self._after_add_player_response(player, utterance)

    def _after_add_player_response(self, player: Player, utterance: str):
        """
        Hook

        Add the utterance to other player's history, if necessary.
        To do this use the method add_user_message(other_player,utterance).

        :param player: that produced the response (or has been modified by the GM)
        :param utterance: that has been added
        """
        pass

    def _validate_player_response(self, player: Player, utterance: str) -> bool:
        """
        Hook

        Decide if an utterance should be added.

        This is also the place to check for game end conditions.

        :param player: for which the response is added as "assistant" to the history
        :param utterance: to be added
        :return: the True, if the utterance is fine; False, if the response should not be added to the history
        """
        return True

    def __parse_response(self, player: Player, utterance: str) -> str:
        _utterance, log_action = self._on_parse_response(player, utterance)
        if _utterance == utterance:
            return utterance
        if log_action:
            action = {'type': 'parse', 'content': _utterance}
            self.log_event(from_="GM", to="GM", action=action)
        return _utterance

    def _on_parse_response(self, player: Player, utterance: str) -> Tuple[str, bool]:
        """
        Hook

        Decide if a response utterance should be modified. If not simply return the utterance.

        When a modified utterance and a true value is returned, then a 'parse' event is logged.

        :param player: that produced the response
        :param utterance: to be potentially modified
        :return: the (modified) utterance and if to log the parse action (default: True)
        """
        return utterance, True

    def _on_before_turn(self, turn_idx: int):
        """
        Hook
        """
        pass

    def _on_after_turn(self, turn_idx: int):
        """
        Hook
        """
        pass

    def __player_sequence(self) -> List[Player]:
        # basic implementation: return players in the order they are added
        return self.get_players()

    def _does_game_proceed(self) -> bool:
        """
        Template method: must be implemented
        """
        raise NotImplementedError()

    def _on_before_game(self):
        """
        Hook
        """
        pass

    def _on_after_game(self):
        """
        Hook
        """
        pass


class GameBenchmark(GameResourceLocator):
    """
    The GameBenchmark organizes the run of a particular collection of game instances
    which compose a benchmark for the game. It supports different experiment conditions for games.
    """

    def __init__(self, name: str):
        super().__init__(name)
        self.instances = None
        self.filter_experiment: List[str] = []

    def get_description(self) -> str:
        """
        A short string describing the game. Will be shown when listing the games.
        :return: game description
        """
        raise NotImplementedError()

    def setup(self, game_path: str, instances_name: str = None):
        self.game_dir = game_path
        self.instances = self.load_instances(game_path, instances_name)

    def build_transcripts(self, results_dir: str = None):
        results_root = file_utils.results_root(results_dir)
        dialogue_partners = [file for file in os.listdir(results_root)
                             if os.path.isdir(os.path.join(results_root, file))]
        for dialogue_pair in dialogue_partners:
            game_result_path = self.results_path_for(results_root, dialogue_pair)
            if not os.path.exists(game_result_path) or not os.path.isdir(game_result_path):
                stdout_logger.info("No results directory found at: " + game_result_path)
                continue

            experiment_dirs = [file for file in os.listdir(game_result_path)
                               if os.path.isdir(os.path.join(game_result_path, file))]
            if not experiment_dirs:
                stdout_logger.warning(f"{self.name}: No experiments for {dialogue_pair}")
            for experiment_dir in experiment_dirs:
                experiment_path = os.path.join(game_result_path, experiment_dir)
                experiment_name = "_".join(experiment_dir.split("_")[1:])  # remove leading index number
                if self.filter_experiment and experiment_name not in self.filter_experiment:
                    stdout_logger.info(f"Skip experiment {experiment_name}")
                    continue
                stdout_logger.info(f"Transcribe: {experiment_name}")
                experiment_config = self.load_results_json(f"{experiment_dir}/experiment_{experiment_name}",
                                                           results_root, dialogue_pair)
                episode_dirs = [file for file in os.listdir(experiment_path)
                                if os.path.isdir(os.path.join(experiment_path, file))]
                error_count = 0
                for episode_dir in tqdm(episode_dirs, desc="Building transcripts"):
                    try:
                        rel_episode_path = f"{experiment_dir}/{episode_dir}"
                        game_instance = self.load_results_json(f"{rel_episode_path}/instance",
                                                               results_root, dialogue_pair)
                        game_interactions = self.load_results_json(f"{rel_episode_path}/interactions",
                                                                   results_root, dialogue_pair)

                        transcript = transcript_utils.build_transcript(game_interactions, experiment_config,
                                                                       game_instance, dialogue_pair)
                        self.store_results_file(transcript, "transcript.html",
                                                dialogue_pair,
                                                sub_dir=rel_episode_path,
                                                root_dir=results_root)
                        transcript_tex = transcript_utils.build_tex(game_interactions)
                        self.store_results_file(transcript_tex, "transcript.tex",
                                                dialogue_pair,
                                                sub_dir=rel_episode_path,
                                                root_dir=results_root)
                    except Exception:  # continue with other episodes if something goes wrong
                        self.logger.exception(f"{self.name}: Cannot transcribe {episode_dir} (but continue)")
                        error_count += 1
                if error_count > 0:
                    stdout_logger.error(
                        f"{self.name}: '{error_count}' exceptions occurred: See clembench.log for details.")

    def compute_scores(self, results_dir: str = None):
        results_root = file_utils.results_root(results_dir)
        dialogue_partners = [file for file in os.listdir(results_root)
                             if os.path.isdir(os.path.join(results_root, file))]
        for dialogue_pair in dialogue_partners:
            game_result_path = self.results_path_for(results_root, dialogue_pair)
            if not os.path.exists(game_result_path) or not os.path.isdir(game_result_path):
                stdout_logger.info("No results directory found at: " + game_result_path)
                continue

            experiment_dirs = [file for file in os.listdir(game_result_path)
                               if os.path.isdir(os.path.join(game_result_path, file))]
            if not experiment_dirs:
                stdout_logger.warning(f"{self.name}: No experiments for {dialogue_pair}")
            for experiment_dir in experiment_dirs:
                experiment_path = os.path.join(game_result_path, experiment_dir)
                experiment_name = "_".join(experiment_dir.split("_")[1:])  # remove leading index number
                if self.filter_experiment and experiment_name not in self.filter_experiment:
                    stdout_logger.info(f"Skip experiment {experiment_name}")
                    continue
                stdout_logger.info(f"Scoring: {experiment_name}")
                experiment_config = self.load_results_json(f"{experiment_dir}/experiment_{experiment_name}",
                                                           results_root, dialogue_pair)
                episode_dirs = [file for file in os.listdir(experiment_path)
                                if os.path.isdir(os.path.join(experiment_path, file))]
                error_count = 0
                for episode_dir in tqdm(episode_dirs, desc="Scoring episodes"):
                    try:
                        rel_episode_path = f"{experiment_dir}/{episode_dir}"
                        game_instance = self.load_results_json(f"{rel_episode_path}/instance",
                                                               results_root, dialogue_pair)
                        game_interactions = self.load_results_json(f"{rel_episode_path}/interactions",
                                                                   results_root, dialogue_pair)

                        game_scorer = self.create_game_scorer(experiment_config, game_instance)
                        game_scorer.compute_scores(game_interactions)
                        game_scorer.store_scores(results_root, dialogue_pair, rel_episode_path)
                    except Exception:  # continue with other episodes if something goes wrong
                        self.logger.exception(f"{self.name}: Cannot score {episode_dir} (but continue)")
                        error_count += 1
                if error_count > 0:
                    stdout_logger.error(
                        f"{self.name}: '{error_count}' exceptions occurred: See clembench.log for details.")

    def run(self, player_models: List[backends.Model], results_dir: str = None):
        """
        Runs game-play on all game instances for a game.
        There must be an instances.json with the following structure:
        "experiments": [ # this is required
            {
                "name": <experiment-name>, # this is required
                "param1": "value1", # optional
                "param2": "value2", # optional
                "game_instances": [ # this is required
                    {"game_id": <value>, "initial_prompt": ... },
                    {"game_id": <value>, "initial_prompt": ... }
                ]
            }
        ]

        The instances will be automatically stored in "game-name" with the following structure:
            - results
                - pairing
                    - game-name
                        - experiment_name
                            - experiment.json
                            - episode_id
                                - instance.json
                                - interaction.json
        """
        results_root = file_utils.results_root(results_dir)
        experiments: List = self.instances["experiments"]
        if not experiments:
            self.logger.warning(f"{self.name}: No experiments for %s", self.name)
        total_experiments = len(experiments)
        for experiment_idx, experiment in enumerate(experiments):
            experiment_name = experiment['name']
            if self.filter_experiment and experiment_name not in self.filter_experiment:
                stdout_logger.info(f"Skip experiment {experiment_idx + 1} of {total_experiments}: {experiment_name}")
                continue
            stdout_logger.info(f"Run experiment {experiment_idx + 1} of {total_experiments}: {experiment_name}")
            # Determine dialogue partners: How often to run the experiment with different partners
            dialogue_partners: List[List[backends.Model]] = []

            if player_models:  # favor runtime argument over experiment config
                dialogue_partners = [player_models]
            elif "dialogue_partners" in experiment:  # edge-case when names are given in experiment config
                for dialogue_pair_names in experiment["dialogue_partners"]:
                    player_models = []
                    for model_name in dialogue_pair_names:
                        player_model = backends.get_model_for(model_name)
                        player_models.append(player_model)
                    dialogue_partners.append(player_models)
                self.logger.info(f"{self.name}: Detected 'dialogue_partners' in experiment config. "
                                 f"Will run with: {dialogue_partners}")

            if not dialogue_partners:
                message = (f"{self.name}: Neither 'dialogue_partners' set in experiment instance"
                           f" nor 'models' given as run arg")
                stdout_logger.error(message)
                raise ValueError(message)

            for dialogue_pair in dialogue_partners:
                if self.is_single_player():
                    if len(dialogue_pair) > 1:
                        message = f"Too many player for singe-player game '{self.name}': '{len(dialogue_partners)}'"
                        stdout_logger.error(message)
                        raise ValueError(message)
                    model_0 = dialogue_pair[0]
                    model_0 = f"{model_0.get_name()}-t{model_0.get_temperature()}"
                    # still we store to model--model dir (virtual self-play)
                    dialogue_pair_desc = f"{model_0}--{model_0}"
                else:  # 2-players
                    if len(dialogue_pair) > 2:
                        message = f"Too many player for two-player game '{self.name}': '{len(dialogue_partners)}'"
                        stdout_logger.error(message)
                        raise ValueError(message)
                    if len(dialogue_pair) == 1:
                        dialogue_pair.append(dialogue_pair[0])  # model expansion
                    model_0 = dialogue_pair[0]
                    model_0 = f"{model_0.get_name()}-t{model_0.get_temperature()}"
                    model_1 = dialogue_pair[1]
                    model_1 = f"{model_1.get_name()}-t{model_1.get_temperature()}"
                    dialogue_pair_desc = f"{model_0}--{model_1}"
                episode_counter = 0

                self.logger.info("Activity: %s Experiment: %s Partners: %s Episode: %d",
                                 self.name, experiment_name, dialogue_pair_desc, episode_counter)

                experiment_record_dir = f"{experiment_idx}_{experiment_name}"
                experiment_config = {k: experiment[k] for k in experiment if k != 'game_instances'}

                # Add some important infos to track
                experiment_config["timestamp"] = datetime.now().isoformat()
                experiment_config["dialogue_partners"] = dialogue_pair_desc

                self.store_results_file(experiment_config,
                                        f"experiment_{experiment_name}.json",
                                        dialogue_pair_desc,
                                        sub_dir=experiment_record_dir,
                                        root_dir=results_root)

                error_count = 0
                time_experiment_start = datetime.now()
                game_instances: List = experiment["game_instances"]
                for game_instance in tqdm(game_instances, desc="Playing games"):
                    game_id = game_instance["game_id"]
                    self.logger.info("Activity: %s Experiment: %s Episode: %d Game: %s",
                                     self.name, experiment_name, episode_counter, game_id)
                    episode_dir = experiment_record_dir + f"/episode_{episode_counter}"
                    self.store_results_file(game_instance,
                                            f"instance.json",
                                            dialogue_pair_desc,
                                            sub_dir=episode_dir,
                                            root_dir=results_root)
                    try:
                        game_master = self.create_game_master(experiment_config, dialogue_pair)
                        game_master.setup(**game_instance)
                        game_master.play()
                        game_master.store_records(results_root, dialogue_pair_desc, episode_dir)
                    except Exception:  # continue with other episodes if something goes wrong
                        self.logger.exception(f"{self.name}: Exception for episode {game_id} (but continue)")
                        error_count += 1
                    episode_counter += 1
                if error_count > 0:
                    stdout_logger.error(
                        f"{self.name}: '{error_count}' exceptions occurred: See clembench.log for details.")
                # Add experiment duration and overwrite file
                time_experiment_end = datetime.now() - time_experiment_start
                experiment_config["duration"] = str(time_experiment_end)
                self.store_results_file(experiment_config,
                                        f"experiment_{experiment_name}.json",
                                        dialogue_pair_desc,
                                        sub_dir=experiment_record_dir,
                                        root_dir=results_root)

    def is_single_player(self) -> bool:
        """
        Decide if only a single cLLM is part of the interaction.

        :return: true, when '-m all' should not try all model combinations, but only all models individually
        """
        return False

    def create_game_master(self, experiment: Dict, player_models: List[backends.Model]) -> GameMaster:
        raise NotImplementedError()

    def create_game_scorer(self, experiment: Dict, game_instance: Dict) -> GameScorer:
        raise NotImplementedError()


class GameInstanceGenerator(GameResourceLocator):
    """
    Create all game instances for a game benchmark.

    Results in a instances.json with the following structure:

    "experiments": [ # this is required
        {
            "name": <experiment-name>, # this is required
            "param1": "value1", # optional
            "param2": "value2", # optional
            "game_instances": [ # this is required
                {"id": <value>, "initial_prompt": ... },
                {"id": <value>, "initial_prompt": ... }
            ]
        }
    ]
    """

    def __init__(self, name: str):
        super().__init__(name)
        self.instances = dict(experiments=list())

    def add_experiment(self, experiment_name: str, dialogue_partners: List[Tuple[str, str]] = None) -> Dict:
        """
        Call this method and adjust the returned dict to configure the experiment.
        For game instances use add_game_instance!
        :param experiment_name: of the new game instance
        :param dialogue_partners: a list of partner definitions for which the experiment will run
        :return: a new game instance dict
        """
        experiment = collections.OrderedDict(name=experiment_name)
        if dialogue_partners:
            experiment["dialogue_partners"] = dialogue_partners
        experiment["game_instances"] = list()
        self.instances["experiments"].append(experiment)
        return experiment

    def add_game_instance(self, experiment: Dict, game_id):
        """
        Call this method and adjust the returned dict to configure the instance.
        :param experiment: to which a new game instance should be added
        :param game_id: of the new game instance
        :return: a new game instance dict
        """
        game_instance = dict(game_id=game_id)
        experiment["game_instances"].append(game_instance)
        return game_instance

    def on_generate(self, **kwargs):
        """
        Game-specific instance generation.
        """
        raise NotImplementedError()

    def generate(self, filename="instances.json", **kwargs):
        self.on_generate(**kwargs)
        self.store_file(self.instances, filename, sub_dir="in")


def is_game(obj):
    # check whether a class inherited from GameBenchmark
    if inspect.isclass(obj) and issubclass(obj, GameBenchmark):
        return True
    return False


def load_game(game_spec: GameSpec, do_setup: bool = True, instances_name: str = None) -> GameBenchmark:
    # append game directory to system path for loading game specific dependencies
    sys.path.insert(0, game_spec.game_path)
    # load game module from this master file
    spec = importlib.util.spec_from_file_location(game_spec["game_name"], game_spec.get_game_file())
    game_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(game_module)

    # extract game class (must inherit from GameBenchmark)
    game_subclasses = inspect.getmembers(game_module, predicate=is_game)
    if len(game_subclasses) == 0:
        raise LookupError(f"There is no GameBenchmark defined in {game_module}. "
                          f"Create such a class and try again.")
    if len(game_subclasses) > 2:
        # currently it finds the super class GameBenchmark and the specific game class (like TabooGameBenchmark)
        # if this is removed from the framework (if this is possible/desired), the check should be > 1
        raise LookupError(f"There is more than one Game defined in {game_module}.")
    for game_name, game_class in game_subclasses:
        # ignore the super class GameBenchmark
        # see comment above, this loop could become redundant (though it also shouldn't hurt)
        if game_name == "GameBenchmark":
            continue
        game_cls = game_class()  # instantiate the specific game class

        if do_setup:
            game_cls.setup(game_spec["game_path"], instances_name)

        return game_cls

