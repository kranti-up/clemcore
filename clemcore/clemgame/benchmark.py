import glob
import importlib.util
import inspect
import logging
import os
import random
import sys
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import List, Dict, ContextManager, Tuple
from tqdm import tqdm

from clemcore import backends
from clemcore.clemgame.master import GameMaster
from clemcore.clemgame.metrics import GameScorer
from clemcore.clemgame.recorder import GameRecorder, DefaultGameRecorder
from clemcore.clemgame.registry import GameSpec
from clemcore.clemgame.resources import GameResourceLocator, store_results_file, load_json

module_logger = logging.getLogger(__name__)
stdout_logger = logging.getLogger("clemcore.run")


class GameInstanceIterator:
    """Class to iterate over game instances."""
    def __init__(self, instances, do_shuffle=False, reset=True):
        """
        Args:
            instances: A list of instances.
            do_shuffle: If True, the order of instances will be randomly shuffled on resetting a GameInstanceIterator
                object.
            reset: If True, GameInstanceIterator object gets reset when in initialized.
        """
        assert instances is not None, "Instances must be given"
        self._instances = instances
        self._do_shuffle = do_shuffle
        self._queue = []
        if reset:
            self.reset()

    def __iter__(self):
        return self

    def __next__(self) -> Tuple[Dict, Dict]:
        try:
            return self._queue.pop(0)
        except IndexError:
            raise StopIteration()

    def __len__(self):
        return len(self._queue)

    def clone(self) -> "GameInstanceIterator":
        """Clone GameInstanceIterator object, creating an exact copy without references to the original."""
        _clone = GameInstanceIterator(self._instances, do_shuffle=self._do_shuffle, reset=False)
        _clone._queue = deepcopy(self._queue)
        return _clone

    def reset(self) -> "GameInstanceIterator":
        """Reset GameInstanceIterator object."""
        self._queue = []
        for index, experiment in enumerate(self._instances["experiments"]):
            filtered_experiment = {k: experiment[k] for k in experiment if k != 'game_instances'}
            filtered_experiment["index"] = index
            for game_instance in experiment["game_instances"]:
                self._queue.append((filtered_experiment, game_instance))
        if self._do_shuffle:
            random.shuffle(self._queue)
        return self


class GameBenchmark(GameResourceLocator):
    """Organizes the run of a particular collection of game instances which compose a benchmark for the game.
    Supports different experiment conditions for games.
    """

    def __init__(self, game_spec: GameSpec):
        """
        Args:
            game_spec: The name of the game (as specified in game_registry)
        """
        super().__init__(game_spec["game_name"], game_spec["game_path"])
        self.game_spec = game_spec
        self.instances = None
        self.filter_experiment: List[str] = []
        self.is_single_player = True if game_spec["players"] == "one" else False

    def setup(self, instances_name: str = None):
        """Set up a benchmark run of a clemgame.
        Args:
            instances_name: Name of the instances JSON file to be used for the benchmark run.
        """
        if instances_name:
            self.instances = self.load_instances(instances_name)
        elif hasattr(self.game_spec, 'instances'):
            self.instances = self.load_instances(self.game_spec.instances)
        else:
            self.instances = self.load_instances("instances")  # fallback to instances.json default

    def create_game_instance_iterator(self, shuffle_instances: bool = False):
        """Create a GameInstanceIterator object for running a game.
        Args:
            shuffle_instances: If True, instances are randomly shuffled.
        Returns:
            A GameInstanceIterator object.
        """
        return GameInstanceIterator(self.instances, do_shuffle=shuffle_instances)

    def compute_scores(self, results_dir: str):
        """Compute and store scores for each episode and player pair.
        Episode score JSON files are stored in each corresponding episode directory. Combined scores for a player/model
        pair are stored in the player pair directory.
        Args:
            results_dir: Path to the results directory.
        """
        results_root = results_dir
        filter_games = [self.game_name]
        interaction_files = glob.glob(os.path.join(results_root, '**', 'interactions.json'), recursive=True)
        if filter_games:
            interaction_files = [interaction_file for interaction_file in interaction_files
                                 if any(game_name in interaction_file for game_name in filter_games)]
        stdout_logger.info(f"Found {len(interaction_files)} interaction files to score. "
                           f"Games: {filter_games if filter_games else 'all'}")
        error_count = 0
        for interaction_file in tqdm(interaction_files, desc="Scoring episodes"):
            try:
                interactions = load_json(interaction_file)
                interactions_dir = Path(interaction_file).parent
                instance = load_json(os.path.join(interactions_dir, "instance.json"))  # sibling file
                experiment_dir = interactions_dir.parent
                experiment = load_json(os.path.join(experiment_dir, "experiment.json"))  # parent file

                game_scorer = self.create_game_scorer(experiment, instance)
                game_scorer.compute_scores(interactions)
                game_scorer.store_scores(interactions_dir)  # store scores.json as sibling file
            except Exception:  # continue with other episodes if something goes wrong
                module_logger.exception(f"{self.game_name}: Cannot score {interaction_file} (but continue)")
                error_count += 1
        if error_count > 0:
            stdout_logger.error(
                f"{self.game_name}: '{error_count}' exceptions occurred: See clembench.log for details.")

    def run(self, player_models: List[backends.Model], results_dir: str):
        """Runs game-play on all game instances for a game.
        There must be an instances.json with the following structure:
        "experiments": [ # this is required
            {
                "name": <experiment-name>, # this is required
                "param1": "value1", # optional
                "param2": "value2", # optional
                "game_instances": [ # this is required
                    {"game_id": <value>, "initial_prompt": ... },
                    {"game_id": <value>, "initial_prompt": ... }
                ]
            }
        ]

        The instances will be automatically stored in "game-name" with the following structure:
            - results
                - pairing
                    - game-name
                        - experiment_name
                            - experiment.json
                            - episode_id
                                - instance.json
                                - interaction.json

        Args:
            player_models: A list of backends.Model instances to run the game with.
            results_dir: Path to the results directory.
        """
        results_root = results_dir
        experiments: List = self.instances["experiments"]
        if not experiments:
            module_logger.warning(f"{self.game_name}: No experiments for %s", self.game_name)
            return
        dialogue_pair_desc = self.get_dialogue_pair_descriptor(player_models)
        total_experiments = len(experiments)
        for experiment_idx, experiment in enumerate(experiments):
            experiment_name = experiment['name']
            if self.filter_experiment and experiment_name not in self.filter_experiment:
                stdout_logger.info(f"Skip experiment {experiment_name} ({experiment_idx + 1}/{total_experiments})")
                continue
            stdout_logger.info(f"Run experiment {experiment_name} ({experiment_idx + 1}/{total_experiments})")

            experiment_config = {k: experiment[k] for k in experiment if k != 'game_instances'}
            experiment_config["timestamp"] = datetime.now().isoformat()
            experiment_config["dialogue_partners"] = dialogue_pair_desc

            experiment_record_dir = f"{experiment_idx}_{experiment_name}"
            store_results_file(self.game_name, experiment_config,
                               f"experiment.json",
                               dialogue_pair_desc,
                               sub_dir=experiment_record_dir,
                               results_dir=results_root)

            episode_counter = 0
            error_count = 0
            time_experiment_start = datetime.now()
            game_instances: List = experiment["game_instances"]
            module_logger.info("Activity: %s Experiment: %s Partners: %s Episodes: %d",
                               self.game_name, experiment_name, dialogue_pair_desc, len(game_instances))
            for game_instance in tqdm(game_instances, desc="Playing games"):
                game_id = game_instance["game_id"]
                module_logger.info("Activity: %s Experiment: %s Episode: %d Game: %s",
                                   self.game_name, experiment_name, episode_counter, game_id)
                episode_dir = experiment_record_dir + f"/episode_{episode_counter}"
                store_results_file(self.game_name, game_instance,
                                   f"instance.json",
                                   dialogue_pair_desc,
                                   sub_dir=episode_dir,
                                   results_dir=results_root)
                game_recorder = DefaultGameRecorder(self.game_name,
                                                    experiment_name,  # meta info for transcribe
                                                    game_id,  # meta info for transcribe
                                                    dialogue_pair_desc)  # meta info for transcribe
                try:
                    game_master = self.create_game_master(experiment_config, player_models)
                    game_master.game_recorder = game_recorder
                    game_master.setup(**game_instance)
                    game_master.play()
                    game_master.store_records(results_root, dialogue_pair_desc, episode_dir)
                except Exception:  # continue with other episodes if something goes wrong
                    module_logger.exception(f"{self.game_name}: Exception for episode {game_id} (but continue)")
                    error_count += 1
                episode_counter += 1
            if error_count > 0:
                stdout_logger.error(
                    f"{self.game_name}: '{error_count}' exceptions occurred: See clembench.log for details.")
            # Add experiment duration and overwrite file
            time_experiment_end = datetime.now() - time_experiment_start
            experiment_config["duration"] = str(time_experiment_end)
            store_results_file(self.game_name, experiment_config,
                               f"experiment.json",
                               dialogue_pair_desc,
                               sub_dir=experiment_record_dir,
                               results_dir=results_root)

    def get_dialogue_pair_descriptor(self, player_models: List[backends.Model]):
        if self.is_single_player:
            if len(player_models) > 1:
                message = f"Too many player for singe-player game '{self.game_name}': '{len(player_models)}'"
                stdout_logger.error(message)
                raise ValueError(message)
            model_0 = player_models[0]
            model_0 = f"{model_0.get_name()}-t{model_0.get_temperature()}"
            # still we store to model--model dir (virtual self-play)
            dialogue_pair_desc = f"{model_0}--{model_0}"
        else:  # 2-players
            if len(player_models) > 2:
                message = f"Too many player for two-player game '{self.game_name}': '{len(player_models)}'"
                stdout_logger.error(message)
                raise ValueError(message)
            if len(player_models) == 1:
                player_models.append(player_models[0])  # model expansion
            model_0 = player_models[0]
            model_0 = f"{model_0.get_name()}-t{model_0.get_temperature()}"
            model_1 = player_models[1]
            model_1 = f"{model_1.get_name()}-t{model_1.get_temperature()}"
            dialogue_pair_desc = f"{model_0}--{model_1}"
        return dialogue_pair_desc

    def create_game_master(self, experiment: Dict, player_models: List[backends.Model]) -> GameMaster:
        """Create a game-specific GameMaster subclass instance to run the game with.
        Must be implemented!
        Args:
            experiment: The experiment (set of instances) to run.
            player_models: Player models to use for one or two players.
        Returns:
            A game-specific GameMaster subclass instance.
        """
        raise NotImplementedError()

    def create_game_scorer(self, experiment: Dict, game_instance: Dict) -> GameScorer:
        """Create a game-specific GameScorer subclass instance to score benchmark records with.
        Must be implemented!
        Args:
            experiment: The experiment (set of instances) to score.
            game_instance: The game instance to score.
        Returns:
            A game-specific GameScorer subclass instance.
        """
        raise NotImplementedError()


def is_game_benchmark(obj):
    """Check whether a class inherited from GameBenchmark.
    Args:
        obj: The object instance to check.
    Returns:
        True if the passed object is a subclass of GameBenchmark, False otherwise.
    """
    if inspect.isclass(obj) and issubclass(obj, GameBenchmark) and obj is not GameBenchmark:
        return True
    return False


@contextmanager
def load_from_spec(game_spec: GameSpec, do_setup: bool = True, instances_name: str = None) \
        -> ContextManager[GameBenchmark]:
    """Load a clemgame using a GameSpec.
    Args:
        game_spec: A GameSpec instance holding specific clemgame data.
        do_setup: Determines if the clemgame's setup method will be executed upon loading.
        instances_name: The name of the instances file to be used for the clemgame's setup if do_setup is True.
    """
    stdout_logger.info("Loading game benchmark for %s", game_spec.game_name)
    # add parent directory to python path if matching naming convention to load additional files if necessary
    parent_path = os.path.dirname(os.path.abspath(game_spec.game_path))
    parent_dir_name = os.path.basename(os.path.normpath(parent_path))
    game_dir_name = os.path.basename(os.path.normpath(game_spec.game_path))
    if game_dir_name.startswith(parent_dir_name):
        stdout_logger.debug("Temporarily added game parent directory to python path: %s", parent_path)
        sys.path.insert(0, parent_path)

    # append game directory to system path for loading game specific dependencies
    sys.path.insert(0, game_spec.game_path)

    # keep track of potentially additional modules which must be unloaded after the run
    before_load = set(sys.modules.keys())

    # load game module from this master file
    spec = importlib.util.spec_from_file_location(game_spec.game_name, game_spec.get_game_file())
    game_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(game_module)

    # cleanup python path again
    if game_dir_name.startswith(parent_dir_name):
        sys.path.remove(parent_path)
    sys.path.remove(game_spec.game_path)
    stdout_logger.info("Removed temporarily added python paths")

    after_load = set(sys.modules.keys())
    extra_modules = after_load - before_load
    if extra_modules:
        stdout_logger.info("Temporarily loaded additional game modules: %s", extra_modules)

    try:
        # extract game class from master.py (is_game checks inheritance from GameBenchmark)
        game_subclasses = inspect.getmembers(game_module, predicate=is_game_benchmark)
        if len(game_subclasses) == 0:
            raise LookupError(f"There is no GameBenchmark defined in {game_module}. "
                              f"Create such a class and try again.")
        if len(game_subclasses) > 1:
            raise LookupError(f"There is more than one Game defined in {game_module}.")
        game_class_name, game_class = game_subclasses[0]
        game_cls = game_class(game_spec)  # instantiate the specific game class

        if do_setup:
            game_cls.setup(instances_name)

        yield game_cls
    finally:
        for mod in extra_modules:
            del sys.modules[mod]
        stdout_logger.info("Removed temporarily loaded additional game modules")
