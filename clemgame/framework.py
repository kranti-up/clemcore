""" Main entry point """
from typing import List, Dict

import backends
import clemgame
from clemgame import game_registry

from datetime import datetime

from clemgame.clemgame import load_games, load_game

logger = clemgame.get_logger(__name__)
stdout_logger = clemgame.get_logger("framework.run")

# look for custom user-defined models before loading the base registry
backends.load_custom_model_registry()
backends.load_model_registry()

# game registry currently loaded in clemgame/__init__.py
# TODO: move here?


def list_games():
    stdout_logger.info("Listing all available games:")
    for game in game_registry:
        stdout_logger.info(f' Game:{game["game_name"]} -> {game["description"]}')


def run(game_or_collection: str, model_specs: List[backends.ModelSpec], gen_args: Dict,
        experiment_name: str = None, instances_name: str = None, results_dir: str = None):
    try:
        player_models = []
        for model_spec in model_specs:
            model = backends.get_model_for(model_spec)
            model.set_gen_args(**gen_args)  # todo make this somehow available in generate method?
            player_models.append(model)
        games = load_games(game_or_collection) #TODO: return filtered game registry (list)
        for game in games:
            #TODO: adapt results_dir and instances_name according to collection
            game_class = load_game(game["game_name"], instances_name=instances_name) # TODO return game object
            logger.info(f'Running benchmark for {game["game_name"]} (models={player_models if player_models is not None else "see experiment configs"})')
            if experiment_name:
                logger.info("Only running experiment: %s", experiment_name)
                game_class.filter_experiment.append(experiment_name)
            time_start = datetime.now()
            game_class.run(player_models=player_models, results_dir=results_dir)
            time_end = datetime.now()
            logger.info(f'Running {game["game_name"]} took {str(time_end - time_start)}')
    except Exception as e:
        stdout_logger.exception(e)
        logger.error(e, exc_info=True)


def score(game_name: str, experiment_name: str = None, results_dir: str = None):
    logger.info("Scoring benchmark for: %s", game_name)
    if experiment_name:
        logger.info("Only scoring experiment: %s", experiment_name)
    if game_name == "all":
        games_list = load_games(do_setup=False) #TODO adapt
    else:
        games_list = [load_game(game_name, do_setup=False)] #TODO adapt
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
        games_list = load_games(do_setup=False) #TODO adapt
    else:
        games_list = [load_game(game_name, do_setup=False)] #TODO adapt
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
