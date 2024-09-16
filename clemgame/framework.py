""" Main entry point """
from typing import List, Dict

import backends
import clemgame

from datetime import datetime

from clemgame.clemgame import load_games, load_game

logger = clemgame.get_logger(__name__)
stdout_logger = clemgame.get_logger("framework.run")

# look for custom user-defined models before loading the base registry
backends.load_custom_model_registry()
backends.load_model_registry()


def list_games():
    print("See clemgame/game_registry.json for available games.")
    stdout_logger.info("See clemgame/game_registry.json for available games.")


def run(game_name: str, model_specs: List[backends.ModelSpec], gen_args: Dict,
        experiment_name: str = None, instances_name: str = None, results_dir: str = None):
    if experiment_name:
        logger.info("Only running experiment: %s", experiment_name)
    try:
        player_models = []
        for model_spec in model_specs:
            model = backends.get_model_for(model_spec)
            model.set_gen_args(**gen_args)  # todo make this somehow available in generate method?
            player_models.append(model)
        game = load_game(game_name, instances_name=instances_name)
        logger.info("Running benchmark for '%s' (models=%s)", game_name,
                    player_models if player_models is not None else "see experiment configs")
        if experiment_name:
            game.filter_experiment.append(experiment_name)
        time_start = datetime.now()
        game.run(player_models=player_models, results_dir=results_dir)
        time_end = datetime.now()
        logger.info(f"Run {game.name} took {str(time_end - time_start)}")
    except Exception as e:
        stdout_logger.exception(e)
        logger.error(e, exc_info=True)


def score(game_name: str, experiment_name: str = None, results_dir: str = None):
    logger.info("Scoring benchmark for: %s", game_name)
    if experiment_name:
        logger.info("Only scoring experiment: %s", experiment_name)
    if game_name == "all":
        games_list = load_games(do_setup=False)
    else:
        games_list = [load_game(game_name, do_setup=False)]
    total_games = len(games_list)
    for idx, game in enumerate(games_list):
        try:
            if experiment_name:
                game.filter_experiment.append(experiment_name)
            stdout_logger.info(f"Score game {idx + 1} of {total_games}: {game.name}")
            time_start = datetime.now()
            game.compute_scores(results_dir)
            time_end = datetime.now()
            logger.info(f"Score {game.name} took {str(time_end - time_start)}")
        except Exception as e:
            stdout_logger.exception(e)
            logger.error(e, exc_info=True)


def transcripts(game_name: str, experiment_name: str = None, results_dir: str = None):
    logger.info("Building benchmark transcripts for: %s", game_name)
    if experiment_name:
        logger.info("Only transcribe experiment: %s", experiment_name)
    if game_name == "all":
        games_list = load_games(do_setup=False)
    else:
        games_list = [load_game(game_name, do_setup=False)]
    total_games = len(games_list)
    for idx, game in enumerate(games_list):
        try:
            if experiment_name:
                game.filter_experiment.append(experiment_name)
            stdout_logger.info(f"Transcribe game {idx + 1} of {total_games}: {game.name}")
            time_start = datetime.now()
            game.build_transcripts(results_dir)
            time_end = datetime.now()
            logger.info(f"Building transcripts {game.name} took {str(time_end - time_start)}")
        except Exception as e:
            stdout_logger.exception(e)
            logger.error(e, exc_info=True)
