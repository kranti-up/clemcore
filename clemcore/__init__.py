""" Main entry point """
import textwrap
from typing import List, Dict, Union
import os.path

import logging.config
import yaml
from datetime import datetime
import json
import importlib.resources as importlib_resources

import clemcore.backends as backends
import clemcore.clemgame as clemgame
import clemcore.utils.file_utils as file_utils
from clemcore.clemgame import GameSpec

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


def load_logging_config():
    pkg_file_path = "utils/logging.yaml"
    with importlib_resources.files(__package__).joinpath(pkg_file_path).open("r") as f:
        return yaml.safe_load(f)


try:
    import logging

    logging.config.dictConfig(load_logging_config())
except Exception as e:
    print(f"Failed to load logging config: {e}")

logger = logging.getLogger(__name__)
stdout_logger = logging.getLogger("clemcore.run")

# look for custom user-defined models before loading the base registry
backends.load_custom_model_registry()
backends.load_model_registry()


def list_games(context_path: str):
    """List all games specified in the game registries.
    Only loads those for which master.py can be found in the specified path.
    See game registry doc for more infos (TODO: add link)
    TODO: add filtering options to see only specific games
    """
    print("Listing all available games")
    game_registry = clemgame.load_game_registry_dynamic(context_path)
    if not game_registry:
        print("No clemgames found under context path:", context_path)
        print("Make sure that your clemgame directory have a clemgame.json")
        print("or register them with 'clem register <your-game-directory>'.")
        return
    for game in game_registry:
        game_name = f'{game["game_name"]}:\n'
        preferred_width = 70
        wrapper = textwrap.TextWrapper(initial_indent="\t", width=preferred_width,
                                       subsequent_indent="\t")
        print(game_name, wrapper.fill(game["description"]))


def run(game: Union[str, Dict, GameSpec], model_specs: List[backends.ModelSpec], gen_args: Dict,
        experiment_name: str = None, instances_name: str = None, results_dir: str = None):
    """Run specific model/models with a specified clemgame.
    Args:
        game: Name of the game, matching the game's name in the game registry, OR GameSpec-like dict, OR GameSpec.
        model_specs: A list of backends.ModelSpec instances for the player models to run the game with.
        gen_args: Text generation parameters for the backend; output length and temperature are implemented for the
            majority of model backends.
        experiment_name: Name of the experiment to run. Corresponds to the experiment key in the instances JSON file.
        instances_name: Name of the instances JSON file to use for this benchmark run.
        results_dir: Path to the results directory in which to store the episode records.
    """
    try:
        player_models = []
        for model_spec in model_specs:
            model = backends.get_model_for(model_spec)
            model.set_gen_args(**gen_args)  # todo make this somehow available in generate method?
            player_models.append(model)

        game_specs = clemgame.select_game(game, game_registry)
        print("Matched game specs in registry:", " ".join([game_spec.game_name for game_spec in game_specs]))
        for game_spec in game_specs:
            game_benchmark = clemgame.load_game(game_spec, instances_name=instances_name)
            logger.info(
                f'Running {game_spec["game_name"]} (models={player_models if player_models is not None else "see experiment configs"})')
            stdout_logger.info(f"Running game {game_spec['game_name']}")
            if experiment_name:  # leaving this as-is for now, needs discussion conclusions
                logger.info("Only running experiment: %s", experiment_name)
                game_benchmark.filter_experiment.append(experiment_name)
            time_start = datetime.now()
            game_benchmark.run(player_models=player_models, results_dir=results_dir)
            time_end = datetime.now()
            logger.info(f'Running {game_spec["game_name"]} took {str(time_end - time_start)}')

    except Exception as e:
        stdout_logger.exception(e)
        logger.error(e, exc_info=True)


def score(game: Union[str, Dict, GameSpec], experiment_name: str = None, results_dir: str = None):
    """Calculate scores from a game benchmark run's records and store score files.
    Args:
        game: Name of the game, matching the game's name in the game registry, OR GameSpec-like dict, OR GameSpec.
        experiment_name: Name of the experiment to score. Corresponds to the experiment directory in each player pair
            subdirectory in the results directory.
        results_dir: Path to the results directory in which the benchmark records are stored.
    """
    logger.info(f"Scoring game {game}")
    stdout_logger.info(f"Scoring game {game}")

    if experiment_name:
        logger.info("Only scoring experiment: %s", experiment_name)
    game_specs = clemgame.select_game(game)
    for game_spec in game_specs:
        try:
            game = clemgame.load_game(game_spec, do_setup=False)
            if experiment_name:
                game.filter_experiment.append(experiment_name)
            time_start = datetime.now()
            game.compute_scores(results_dir)
            time_end = datetime.now()
            logger.info(f"Scoring {game.game_name} took {str(time_end - time_start)}")
        except Exception as e:
            stdout_logger.exception(e)
            logger.error(e, exc_info=True)


def transcripts(game: Union[str, Dict, GameSpec], experiment_name: str = None, results_dir: str = None):
    """Create episode transcripts from a game benchmark run's records and store transcript files.
    Args:
        game: Name of the game, matching the game's name in the game registry, OR GameSpec-like dict, OR GameSpec.
        experiment_name: Name of the experiment to score. Corresponds to the experiment directory in each player pair
            subdirectory in the results directory.
        results_dir: Path to the results directory in which the benchmark records are stored.
    """
    logger.info(f"Transcribing game {game}")
    stdout_logger.info(f"Transcribing game {game}")
    if experiment_name:
        logger.info("Only transcribing experiment: %s", experiment_name)
    game_specs = clemgame.select_game(game)
    for game_spec in game_specs:
        try:
            game = clemgame.load_game(game_spec, do_setup=False)
            if experiment_name:
                game.filter_experiment.append(experiment_name)
            time_start = datetime.now()
            game.build_transcripts(results_dir)
            time_end = datetime.now()
            logger.info(f"Building transcripts for {game.game_name} took {str(time_end - time_start)}")
        except Exception as e:
            stdout_logger.exception(e)
            logger.error(e, exc_info=True)

