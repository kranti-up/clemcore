from typing import Dict, List

from backends import Model
from clemgame.clemgame import GameBenchmark, GameMaster, GameScorer
from games.dmsystem_monolithic_llm.master import DMSystemMaster, DMSystemScorer
from games.dmsystem_modular_llm.instancegenerator import GAME_NAME
from games.dmsystem_modular_llm.llmsubsystems import LLMSubSystems
from games.dmsystem_modular_llm.players import ModularLLMSpeaker


class DMSystemModularLLMBenchmark(GameBenchmark):
    def __init__(self):
        super().__init__(GAME_NAME)

    def get_description(self):
        return "A simple game in which a speaker collaborate with a bot to complete a task."

    def create_game_master(
        self, experiment: Dict, player_models: List[Model]
    ) -> GameMaster:
        classmethods_dict = {"modules": LLMSubSystems, "speaker": ModularLLMSpeaker}
        return DMSystemMaster(self.name, experiment, player_models, classmethods_dict)

    def create_game_scorer(self, experiment: Dict, game_instance: Dict) -> GameScorer:
        return DMSystemScorer(self.name, experiment, game_instance)

    def is_single_player(self) -> bool:
        return False
