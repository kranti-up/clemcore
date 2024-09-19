import json
import os
import logging
import logging.config
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Dict, List

import yaml

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

    def game_file_exists(self):
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

    def in_collection(self, collection):
        return True if collection in self.collection else False

    def is_multimodal(self):
        return self.image in ["single", "multi"]

    def in_languages(self, lang):
        return True if lang in self.languages else False


def load_custom_game_registry(_game_registry_path: str = None, is_optional=True):
    if not _game_registry_path:
        _game_registry_path = os.path.join(project_root, "clemgame", "game_registry_custom.json")
    load_game_registry(_game_registry_path, is_mandatory=not is_optional)


def load_game_registry(_game_registry_path: str = None, is_mandatory=True):
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
                #TODO: where to log this properly?
                print(f"Game master for {_game_spec.game_name} not found in '{_game_spec}'. "
                    f"Update the game_registry.json (or game_registry_custom.json).")


game_registry: List[GameSpec] = list()  # we store game specs so that games can be loaded dynamically
load_custom_game_registry()
load_game_registry()