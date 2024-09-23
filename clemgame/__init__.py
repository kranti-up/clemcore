import os
import logging
import logging.config
import yaml
import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Dict


BANNER = \
    r"""
      _                _                     _     
     | |              | |                   | |    
  ___| | ___ _ __ ___ | |__   ___ _ __   ___| |__  
 / __| |/ _ \ '_ ` _ \| '_ \ / _ \ '_ \ / __| '_ \ 
| (__| |  __/ | | | | | |_) |  __/ | | | (__| | | |
 \___|_|\___|_| |_| |_|_.__/ \___|_| |_|\___|_| |_|
"""  # doom font, thanks to http://patorjk.com/software/taag/

print(BANNER)

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
game_registry = []  # list of game specs to load from dynamically


# Configure logging
with open(os.path.join(project_root, "logging.yaml")) as f:
    conf = yaml.safe_load(f)
    log_fn = conf["handlers"]["file_handler"]["filename"]
    log_fn = os.path.join(project_root, log_fn)
    conf["handlers"]["file_handler"]["filename"] = log_fn
    logging.config.dictConfig(conf)


def get_logger(name):
    return logging.getLogger(name)


@dataclass(frozen=True)
class GameSpec(SimpleNamespace):
    """
    Base class for game specifications.
    Holds all necessary information to play game in clembench (see README for list of attributes)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # check for required fields
        if "game_name" not in self:
            raise KeyError(f"No game name specified in entry {kwargs}")
        if "game_path" not in self:
            raise KeyError(f"No game path specified in {kwargs}")


    def __repr__(self):
        return f"GameSpec({str(self)})"

    def __str__(self):
        return str(self.__dict__)

    def __getitem__(self, item):
        """ dict-like behavior """
        return getattr(self, item)

    def __contains__(self, attribute):
        """ dict-like behavior """
        return hasattr(self, attribute)

    @classmethod
    def from_dict(cls, spec: Dict):
        """
        Initialize a GameSpec from a dictionary. Can be used to directly create a GameSpec from a game registry entry.
        """
        return cls(**spec)

    def matches(self, spec: Dict):
        """
        Check if the game features match a given specification
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

    def game_file_exists(self):
        """
        Check if master.py can be located at the specified game_path
        """
        if os.path.isabs(self.game_path):
            game_file = os.path.join(self.game_path, "master.py")
        else:
            game_file = os.path.join(project_root, self.game_path, "master.py")
        return True if os.path.isfile(game_file) else False

    def get_game_file(self):
        if os.path.isabs(self.game_path):
            return os.path.join(self.game_path, "master.py")
        else:
            return os.path.join(project_root, self.game_path, "master.py")


def load_custom_game_registry(logger, _game_registry_path: str = None, is_optional=True):
    # optional custom registry loaded first, so that these entries come first in the game registry list
    if not _game_registry_path:
        _game_registry_path = os.path.join(project_root, "clemgame", "game_registry_custom.json")
    load_game_registry(logger, _game_registry_path, is_mandatory=not is_optional)


def load_game_registry(logger, _game_registry_path: str = None, is_mandatory=True):
    if not _game_registry_path:
        _game_registry_path = os.path.join(project_root, "clemgame", "game_registry.json")
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
                logger.warning(f"Game master for {_game_spec.game_name} not found in '{_game_spec['game_path']}'. "
                               f"Game '{_game_spec.game_name}' not added to available games. "
                               f"Update game_registry.json (or game_registry_custom.json) with the right path to include it.")

