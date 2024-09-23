""" Main entry point """
from typing import List, Dict

import backends
import clemgame

from clemgame.clemgame import select_games, load_game

from datetime import datetime

logger = clemgame.get_logger(__name__)
stdout_logger = clemgame.get_logger("framework.run")

# look for custom user-defined models before loading the base registry
backends.load_custom_model_registry()
backends.load_model_registry()

# load available games
clemgame.load_custom_game_registry(stdout_logger)
clemgame.load_game_registry(stdout_logger)


def list_games():
    stdout_logger.info("Listing all available games:")
    for game in clemgame.game_registry:
        stdout_logger.info(f' Game:{game["game_name"]} -> {game["description"]}')


def run(game_or_collection: str, model_specs: List[backends.ModelSpec], gen_args: Dict,
        experiment_name: str = None, instances_name: str = None, results_dir: str = None):
    try:
        player_models = []
        for model_spec in model_specs:
            model = backends.get_model_for(model_spec)
            model.set_gen_args(**gen_args)  # todo make this somehow available in generate method?
            player_models.append(model)

        games_list = select_games(game_or_collection)
        total_games = len(games_list)
        # TODO: return results_dir and instances_name as well according to collection?  [ab]
        for idx,game_spec in enumerate(games_list):
            game = load_game(game_spec, instances_name=instances_name)
            logger.info(f'Running {game_spec["game_name"]} (models={player_models if player_models is not None else "see experiment configs"})')
            if experiment_name:
                # TODO experiment name can only be given for single games, not for collections [ab]
                logger.info("Only running experiment: %s", experiment_name)
                game.filter_experiment.append(experiment_name)
            stdout_logger.info(f"Running game {idx + 1} of {total_games}: {game_spec['game_name']}")
            time_start = datetime.now()
            game.run(player_models=player_models, results_dir=results_dir)
            time_end = datetime.now()
            logger.info(f'Running {game_spec["game_name"]} took {str(time_end - time_start)}')
    except Exception as e:
        stdout_logger.exception(e)
        logger.error(e, exc_info=True)


def score(game_or_collection: str, experiment_name: str = None, results_dir: str = None):
    logger.info("Scoring benchmark for: %s", game_or_collection)
    if experiment_name:
        # TODO experiment name can only be given for single games, not for collections [ab]
        logger.info("Only scoring experiment: %s", experiment_name)
    games_list = select_games(game_or_collection) #TODO adapt
    # TODO: return results_dir as well according to collection?  [ab]
    total_games = len(games_list)
    for idx, game_spec in enumerate(games_list):
        try:
            game = load_game(game_spec, do_setup=False)
            if experiment_name:
                game.filter_experiment.append(experiment_name)
            stdout_logger.info(f"Score game {idx + 1} of {total_games}: {game_spec['game_name']}")
            time_start = datetime.now()
            game.compute_scores(results_dir)
            time_end = datetime.now()
            logger.info(f"Score {game.name} took {str(time_end - time_start)}")
        except Exception as e:
            stdout_logger.exception(e)
            logger.error(e, exc_info=True)


def transcripts(game_or_collection: str, experiment_name: str = None, results_dir: str = None):
    logger.info("Building benchmark transcripts for: %s", game_or_collection)
    if experiment_name:
        # TODO experiment name can only be given for single games, not for collections [ab]
        logger.info("Only transcribe experiment: %s", experiment_name)
    games_list = select_games(game_or_collection)  # TODO adapt
    # TODO: return results_dir as well according to collection?  [ab]
    total_games = len(games_list)
    for idx, game_spec in enumerate(games_list):
        try:
            game = load_game(game_spec, do_setup=False)
            if experiment_name:
                game.filter_experiment.append(experiment_name)
            stdout_logger.info(f"Transcribe game {idx + 1} of {total_games}: {game_spec['game_name']}")
            time_start = datetime.now()
            game.build_transcripts(results_dir)
            time_end = datetime.now()
            logger.info(f"Building transcripts {game.name} took {str(time_end - time_start)}")
        except Exception as e:
            stdout_logger.exception(e)
            logger.error(e, exc_info=True)
