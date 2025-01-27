from typing import Dict, List

from backends import Model
from clemgame.clemgame import GameBenchmark, GameMaster, GameScorer
from games.dmsystem_monolithic_llm.master import DMSystemMaster, DMSystemScorer
from games.dmsystem_customtod.players import CustomTODSpeaker
from games.dmsystem_customtod.interact import Interact
from games.dmsystem_customtod.instancegenerator import GAME_NAME



class DMSystemCustomTODBenchmark(GameBenchmark):
    def __init__(self):
        super().__init__(GAME_NAME)

    def get_description(self):
        return "A simple game in which a human collaborate with a bot to complete a task."

    def create_game_master(
        self, experiment: Dict, player_models: List[Model]
    ) -> GameMaster:
        classmethods_dict = {"modules": Interact, "speaker": CustomTODSpeaker}
        return DMSystemMaster(self.name, experiment, player_models, classmethods_dict)

    def create_game_scorer(self, experiment: Dict, game_instance: Dict) -> GameScorer:
        return DMSystemScorer(self.name, experiment, game_instance)

    def is_single_player(self) -> bool:
        return False
