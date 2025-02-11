import argparse
import textwrap
import logging
from datetime import datetime
from typing import List, Dict, Union

import clemcore.backends as backends
from clemcore.clemgame import GameSpec
import clemgame

logger = logging.getLogger(__name__)
stdout_logger = logging.getLogger("clemcore.cli")


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


def read_gen_args(args: argparse.Namespace):
    """Get text generation inference parameters from CLI arguments.
    Handles sampling temperature and maximum number of tokens to generate.
    Args:
        args: CLI arguments as passed via argparse.
    Returns:
        A dict with the keys 'temperature' and 'max_tokens' with the values parsed by argparse.
    """
    return dict(temperature=args.temperature, max_tokens=args.max_tokens)


def cli(args: argparse.Namespace):
    if args.command_name == "list":
        if args.mode == "games":
            list_games(args.context)
        elif args.mode == "backends":
            ...
        else:
            print(f"Cannot list {args.mode}. Choose an option documented at 'list -h'.")
    if args.command_name == "run":
        run(args.game,
            model_specs=backends.ModelSpec.from_strings(args.models),
            gen_args=read_gen_args(args),
            experiment_name=args.experiment_name,
            instances_name=args.instances_name,
            results_dir=args.results_dir)
    if args.command_name == "score":
        score(args.game, experiment_name=args.experiment_name, results_dir=args.results_dir)
    if args.command_name == "transcribe":
        transcripts(args.game, experiment_name=args.experiment_name, results_dir=args.results_dir)


"""
    Use good old argparse to run the commands.

    To list available games: 
    $> python3 scripts/cli.py list games

    To list available backends: 
    $> python3 scripts/cli.py list backends

    To run a specific game with a single player:
    $> python3 scripts/cli.py run -g privateshared -m mock

    To run a specific game with a two players:
    $> python3 scripts/cli.py run -g taboo -m mock mock

    If the game supports model expansion (using the single specified model for all players):
    $> python3 scripts/cli.py run -g taboo -m mock

    To score all games:
    $> python3 scripts/cli.py score

    To score a specific game:
    $> python3 scripts/cli.py score -g privateshared

    To score all games:
    $> python3 scripts/cli.py transcribe

    To score a specific game:
    $> python3 scripts/cli.py transcribe -g privateshared
"""


def main():
    """Main CLI handling function.

    Handles the clembench CLI commands

    - 'ls' to list available clemgames.
    - 'run' to start a benchmark run. Takes further arguments determining the clemgame to run, which experiments,
    instances and models to use, inference parameters, and where to store the benchmark records.
    - 'score' to score benchmark results. Takes further arguments determining the clemgame and which of its experiments
    to score, and where the benchmark records are located.
    - 'transcribe' to transcribe benchmark results. Takes further arguments determining the clemgame and which of its
    experiments to transcribe, and where the benchmark records are located.

    Args:
        args: CLI arguments as passed via argparse.
    """
    parser = argparse.ArgumentParser()
    sub_parsers = parser.add_subparsers(dest="command_name")
    list_parser = sub_parsers.add_parser("list")
    list_parser.add_argument("mode", choices=["games", "backends"],
                             default="games", nargs="?", type=str,
                             help="Choose between games or backends to be listed. Default: games")
    list_parser.add_argument("context", default=".", nargs="?", type=str,
                             help="A path to a directory that contains a clemgame or game registry file. "
                                  "Can also be called directly from within a clemgame directory with '.'. "
                                  "Default: . (dot).")

    run_parser = sub_parsers.add_parser("run", formatter_class=argparse.RawTextHelpFormatter)
    run_parser.add_argument("context", help="A path to a game directory or game registry file.")
    run_parser.add_argument("-m", "--models", type=str, nargs="*",
                            help="""Assumes model names supported by the implemented backends.

      To run a specific game with a single player:
      $> python3 scripts/cli.py run -g privateshared -m mock

      To run a specific game with a two players:
      $> python3 scripts/cli.py run -g taboo -m mock mock

      If the game supports model expansion (using the single specified model for all players):
      $> python3 scripts/cli.py run -g taboo -m mock

      When this option is not given, then the dialogue partners configured in the experiment are used. 
      Default: None.""")
    run_parser.add_argument("-e", "--experiment_name", type=str,
                            help="Optional argument to only run a specific experiment")
    run_parser.add_argument("-g", "--game", type=str,
                            required=True, help="A specific game name (see ls), or a GameSpec-like JSON string object.")
    run_parser.add_argument("-t", "--temperature", type=float, default=0.0,
                            help="Argument to specify sampling temperature for the models. Default: 0.0.")
    run_parser.add_argument("-l", "--max_tokens", type=int, default=100,
                            help="Specify the maximum number of tokens to be generated per turn (except for cohere). "
                                 "Be careful with high values which might lead to exceed your API token limits."
                                 "Default: 100.")
    run_parser.add_argument("-i", "--instances_name", type=str, default=None,
                            help="The instances file name (.json suffix will be added automatically.")
    run_parser.add_argument("-r", "--results_dir", type=str, default="results",
                            help="A relative or absolute path to the results root directory. "
                                 "For example '-r results/v1.5/de‘ or '-r /absolute/path/for/results'. "
                                 "When not specified, then the results will be located in 'results'")

    score_parser = sub_parsers.add_parser("score")
    score_parser.add_argument("-e", "--experiment_name", type=str,
                              help="Optional argument to only run a specific experiment")
    score_parser.add_argument("-g", "--game", type=str,
                              help='A specific game name (see ls), a GameSpec-like JSON string object or "all" (default).',
                              default="all")
    score_parser.add_argument("-r", "--results_dir", type=str, default="results",
                              help="A relative or absolute path to the results root directory. "
                                   "For example '-r results/v1.5/de‘ or '-r /absolute/path/for/results'. "
                                   "When not specified, then the results will be located in 'results'")

    transcribe_parser = sub_parsers.add_parser("transcribe")
    transcribe_parser.add_argument("-e", "--experiment_name", type=str,
                                   help="Optional argument to only run a specific experiment")
    transcribe_parser.add_argument("-g", "--game", type=str,
                                   help='A specific game name (see ls), a GameSpec-like JSON string object or "all" (default).',
                                   default="all")
    transcribe_parser.add_argument("-r", "--results_dir", type=str, default="results",
                                   help="A relative or absolute path to the results root directory. "
                                        "For example '-r results/v1.5/de‘ or '-r /absolute/path/for/results'. "
                                        "When not specified, then the results will be located in 'results'")

    cli(parser.parse_args())


if __name__ == "__main__":
    main()
