import collections
import json
import os.path
from typing import List, Dict, Union
from types import SimpleNamespace
import logging
import nltk
import clemcore.utils.file_utils as file_utils

logger = logging.getLogger(__name__)
stdout_logger = logging.getLogger("clemcore.cli")


class GameSpec(SimpleNamespace):
    """Base class for game specifications.
    Holds all necessary information to play game in clembench (see README for list of attributes)
    """

    def __init__(self, allow_underspecified: bool = False, **kwargs):
        super().__init__(**kwargs)
        # check for required fields
        if not allow_underspecified:
            if "game_name" not in self:
                raise KeyError(f"No game name specified in entry {kwargs}")
            if "game_path" not in self:
                raise KeyError(f"No game path specified in {kwargs}")
        # make game_path absolute
        if hasattr(self, 'game_path'):
            if not os.path.isabs(self.game_path):
                self.game_path = os.path.join(file_utils.project_root(), self.game_path)

    def __repr__(self):
        """Returns string representation of this GameSpec."""
        return f"GameSpec({str(self)})"

    def __str__(self):
        """Returns GameSpec instance attribute dict as string."""
        return str(self.__dict__)

    def __getitem__(self, item):
        """Access GameSpec instance attributes like dict items.
        Args:
            item: The string name of the instance attribute to get.
        Returns:
            The value of the GameSpec instance attribute, or if the instance does not have the attribute, the string
            passed as argument to this method.
        """
        return getattr(self, item)

    def __contains__(self, attribute):
        """Check GameSpec instance attributes like dict keys.
        Args:
            attribute: The string name of the instance attribute to check for.
        Returns:
            True if the GameSpec instance contains an attribute with the passed string name, False otherwise.
        """
        return hasattr(self, attribute)

    @classmethod
    def from_dict(cls, spec: Dict, allow_underspecified: bool = False):
        """Initialize a GameSpec from a dictionary.
        Can be used to directly create a GameSpec from a game registry entry.
        Args:
            spec: A game-specifying dict.
        Returns:
            A GameSpec instance with the data specified by the passed dict.
        """
        return cls(allow_underspecified, **spec)

    def matches(self, spec: Dict):
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

    def get_game_file(self):
        """Get the file path of the master.py of the game specified by this GameSpec instance.
        Main game file must be called master.py in game directory.
        Returns:
            The file path of the master.py of the game specified by this GameSpec instance as a string.
        """
        return os.path.join(self.game_path, "master.py")

    def game_file_exists(self):
        """Check if master.py can be located at the specified game_path.
        Returns:
            True if the master.py is located at the specified game_path, False otherwise.
        """
        return True if os.path.isfile(self.get_game_file()) else False

    def unify(self, other: "GameSpec") -> "GameSpec":
        """Unify two GameSpec instances.
        Args:
            other: The other GameSpec instance this instance is to be unified with.
        Returns:
            The GameSpec unification of this GameSpec instance and the passed GameSpec instance.
        Raises:
            ValueError: A ValueError exception is raised if the passed GameSpec instance does not unify with this
                GameSpec instance.
        """
        result = nltk.featstruct.unify(self.__dict__, other.__dict__)
        if result is None:
            raise ValueError(f"{self} does not unify with {other}")
        return GameSpec(**result)


def load_game_registry_dynamic(context_path: str):
    if os.path.isfile(context_path):
        return load_game_registry_from_file(context_path)
    return load_game_registry_from_directories(context_path)


def load_game_spec_from_directory(dir_path: str):
    file_path = os.path.join(dir_path, "clemgame.json")
    with open(file_path, encoding='utf-8') as f:
        game_spec = json.load(f)
        game_spec["game_path"] = dir_path
    return GameSpec.from_dict(game_spec)


def load_game_registry_from_directories(context_path: str, max_depth=10):
    def add_subdirectories_as_candidates(dir_path):
        for current_file in os.listdir(dir_path):
            file_path = os.path.join(current_directory, current_file)
            if os.path.isdir(file_path) and not current_file.startswith("."):  # hidden dir
                game_candidates.append((file_path, depth + 1))

    game_registry = []
    game_candidates = collections.deque([(context_path, 0)])
    while game_candidates:
        current_directory, depth = game_candidates.popleft()
        if depth > max_depth:
            continue  # Early stopping to prevent infinite lookups
        try:
            game_spec = load_game_spec_from_directory(current_directory)
            game_registry.append(game_spec)
            add_subdirectories_as_candidates(current_directory)
        except PermissionError:
            continue  # ignore permissions errors
        except FileNotFoundError:
            if current_directory == ".":  # we expect that dot-dir is not necessarily a clemgame
                add_subdirectories_as_candidates(current_directory)
        except Exception as e:  # most likely a problem with the json file
            stdout_logger.warning("Lookup failed at '%s' with exception: %s",
                                  current_directory, e)
    return game_registry


def load_game_registry_from_file(_game_registry_path: str = None, is_mandatory=True):
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
    game_registry = []
    if not _game_registry_path:
        _game_registry_path = os.path.join(file_utils.clemcore_root(), "clemgame", "game_registry.json")
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
            game_registry.append(_game_spec)
    return game_registry


def select_game(game: Union[str, Dict, GameSpec], game_registry) -> List[GameSpec]:
    """Select a list of GameSpecs from the game registry by unifying game spec dict or game name.
    Args:
        game: String name of the game matching the 'game_name' value of the game registry entry to select, OR a
            GameSpec-like dict, OR a GameSpec object.
            A passed GameSpec-like dict can EITHER contain the 'benchmark' key with a list of benchmark versions value,
            in which case all games that have matching benchmark version strings in their 'benchmark' key values are
            selected, OR contain one or more other GameSpec keys, in which case all games that unify with the given key
            values are selected. If there is the 'benchmark' key, only benchmark versions are checked!
            For example: {'benchmark':['v2']} will select all games that have 'v2' in their 'benchmark' key value list.
            {'main_game': 'wordle'} will select all wordle variants, as their game registry entries have the 'main_game'
            key value 'wordle'.
    Returns:
        A list of GameSpec instances from the game registry corresponding to the passed game string, dict or GameSpec.
    Raises:
        ValueError: No game specification matching the passed game was found in the game registry.
    """
    # check if passed game is parseable JSON:
    game_is_dict = False
    try:
        game = game.replace("'", '"')
        game = json.loads(game)
        game_is_dict = True
    except Exception:
        logger.info(f"Passed game '{game}' does not parse as JSON!")
        pass

    # convert passed JSON to GameSpec for unification:
    game_is_gamespec = False
    if game_is_dict:
        game = GameSpec.from_dict(game, allow_underspecified=True)
        game_is_gamespec = True
    elif type(game) == GameSpec:
        game_is_gamespec = True

    if game_is_gamespec:
        matching_registered_games: list = list()
        # iterate over game registry:
        for registered_game_spec in game_registry:

            if hasattr(game, 'benchmark'):
                # passed game spec specifies benchmark version
                for benchmark_version in game.benchmark:
                    if benchmark_version in registered_game_spec.benchmark:
                        if registered_game_spec.game_file_exists():
                            matching_registered_games.append(registered_game_spec)

            else:
                # get unifying entries:
                unifying_game_spec = None
                try:
                    unifying_game_spec = game.unify(registered_game_spec)
                    if unifying_game_spec.game_file_exists():
                        # print(f"Found unifying game registry entry: {unifying_game_spec}")
                        matching_registered_games.append(unifying_game_spec)
                except ValueError:
                    continue

        return matching_registered_games
    elif game == "all":
        return game_registry
    else:
        # return first entry that matches game_name
        for registered_game_spec in game_registry:
            if registered_game_spec["game_name"] == game:
                if registered_game_spec.game_file_exists():
                    return [registered_game_spec]
                else:
                    raise ValueError(f"Game master file master.py not found in {registered_game_spec['game_path']}."
                                     f"Update clemcore/clemgame/game_registry.json (or game_registry_custom.json) with the right path for {registered_game_spec}.")
        raise ValueError(f"No games found matching the given specification '{registered_game_spec}'. "
                         "Make sure the game name matches the name in clemcore/clemgame/game_registry.json (or game_registry_custom.json)")

    # extension to select subset of games
    # (postponed because it introduces more complexity
    # on things like how to specify specific episodes (which could, however be integrated into the game spec
    # and then selected through the custom game_spec for a specific run),
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
