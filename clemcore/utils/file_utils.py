"""
Defines locations within the project structure
and supplies several functions for loading different files
#TODO: check which functions could be moved to ResourceLocator
"""

from typing import Dict
import os
import json
import csv


def project_root():
    """Get the absolute path to main clembench directory.
    Returns:
         The absolute path to main clembench directory as string.
    """
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def clemcore_root():
    """Get the absolute path to the framework directory.
    Returns:
        The absolute path to the framework directory (clembench/framework) as string.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def project_utils():
    """Get the absolute path to the utils directory.
    Returns:
        The absolute path to the utils directory (clembench/utils) as string.
    """
    return os.path.join(clemcore_root(), "utils")


def results_root(results_dir: str = None) -> str:
    """Get the absolute path to the results root directory.
    Args:
        results_dir: The relative path to the results directory inside the clembench directory.
    """
    #if the framework is used via cli.py, the default is actually already set by argparse, so this will not be None
    results_dir = os.path.join(project_root(), "results") if results_dir is None else results_dir
    if os.path.isabs(results_dir):
        return results_dir
    # if not absolute, results_dir is given relative to project root (see default in cli.py)
    # and needs to be transformed
    return os.path.normpath(os.path.join(project_root(), results_dir))


def game_results_dir_for(results_dir: str, dialogue_pair: str, game_name: str) -> str:
    """Get the absolute path to the results directory for a specified game and player pair combination.
    Args:
        results_dir: The relative path to the results directory inside the clembench directory.
        dialogue_pair: The name of the player pair combination directory.
        game_name: The name of the game (directory).
    Returns:
        The absolute path to the results directory for a specified game and player pair combination as string.
    """
    return os.path.join(results_root(results_dir), dialogue_pair, game_name)


def load_json(file_name: str, game_name: str) -> Dict:
    """Load a JSON file from a clemgame.
    Args:
        file_name: Name of the JSON file.
        game_name: The name of the game that the JSON file belongs to.
    Returns:
        A dict of the JSON file content.
    """
    data = load_file(file_name, game_name, file_ending=".json")
    data = json.loads(data)
    return data


def load_csv(file_name: str, game_name: str):
    """Load a CSV file from a clemgame.
    Args:
        file_name: Name of the CSV file.
        game_name: The name of the game that the CSV file belongs to.
    Returns:
        A list version of the CSV file content.
    """
    # iso8859_2 was required for opening nytcrosswords.csv for clues in wordle
    rows = []
    fp = file_path(file_name, game_name)
    with open(fp, encoding='iso8859_2') as csv_file:
        data = csv.reader(csv_file, delimiter=',')
        # header = next(data)
        for row in data:
            rows.append(row)
    return rows


def load_template(file_name: str, game_name: str) -> str:
    """Load a text template file from a clemgame.
    Args:
        file_name: Name of the text template file.
        game_name: The name of the game that the text template file belongs to.
    Returns:
        A string version of the text template file content.
    """
    return load_file(file_name, game_name, file_ending=".template")


def file_path(file_name: str, game_name: str = None) -> str:
    """Get the absolute path to a file.
    Args:
        file_name: Name of the file.
        game_name: The name of the game that the file belongs to.
    Returns:
        The absolute path to the file as string.
    """
    if game_name:
        return os.path.join(game_name, file_name)
    return os.path.join(project_root(), file_name)


def load_file(file_name: str, game_name: str = None, file_ending: str = None) -> str:
    """Load a file from a clemgame.
    Assumes the file to be an utf8-encoded (text) file.
    Args:
        file_name: Name of the file.
        game_name: The name of the game that the file belongs to.
        file_ending: The file type suffix of the file.
    Returns:
        The file content as returned by open->read().
    """
    if file_ending and not file_name.endswith(file_ending):
        file_name = file_name + file_ending
    fp = file_path(file_name, game_name)
    with open(fp, encoding='utf8') as f:
        data = f.read()
    return data


def load_results_json(file_name: str, results_dir: str, dialogue_pair: str, game_name: str) -> Dict:
    """Load a benchmark record JSON file.
    Args:
        file_name: The name of the benchmark record JSON file.
        results_dir: The relative path to the results directory inside the clembench directory.
        dialogue_pair: The name of the player pair combination directory.
        game_name: The name of the game (directory).
    Returns:
        A dict version of the benchmark record JSON file content.
    """
    data = __load_results_file(file_name, results_dir, dialogue_pair, game_name, file_ending=".json")
    data = json.loads(data)
    return data


def __load_results_file(file_name: str, results_dir: str, dialogue_pair: str, game_name: str,
                        file_ending: str = None) -> str:
    """Load a benchmark record file.
    Assumes the file to be an utf8-encoded (text) file.
    Args:
        file_name: The name of the benchmark record file.
        results_dir: The relative path to the results directory inside the clembench directory.
        dialogue_pair: The name of the player pair combination directory.
        game_name: The name of the game (directory).
    Returns:
        The benchmark record file content as a string.
    """
    if file_ending and not file_name.endswith(file_ending):
        file_name = file_name + file_ending
    game_results_dir = game_results_dir_for(results_dir, dialogue_pair, game_name)
    fp = os.path.join(game_results_dir, file_name)
    with open(fp, encoding='utf8') as f:
        data = f.read()
    return data


def store_game_results_file(data, file_name: str, dialogue_pair: str, game_name: str,
                            sub_dir: str = None, root_dir: str = None,
                            do_overwrite: bool = True) -> str:
    """Store a benchmark record file.
    Args:
        data: The benchmark record content to store.
        file_name: The name of the benchmark record file.
        dialogue_pair: The name of the player pair combination directory.
        game_name: The name of the game (directory).
        sub_dir: The results subdirectory to store the file in.
        root_dir: The clembench root directory path. TODO: Check what this actually expects
        do_overwrite: Determines if existing benchmark result file should be overwritten. Default: True
    Returns:
        The stored benchmark record file content as a string.
    """
    game_results_dir = game_results_dir_for(root_dir, dialogue_pair, game_name)
    return store_file(data, file_name, game_results_dir, sub_dir, do_overwrite)


def store_game_file(data, file_name: str, game_name: str, sub_dir: str = None, do_overwrite: bool = True) -> str:
    """Store a game file.
    Args:
        data: The content to store.
        file_name: The name of the file.
        game_name: The name of the game (directory).
        sub_dir: The game subdirectory to store the file in.
        do_overwrite: Determines if existing game file should be overwritten. Default: True
    Returns:
        The stored game file content as a string.
    """
    return store_file(data, file_name, game_dir(game_name), sub_dir, do_overwrite)  # TODO: Missing function?


def store_file(data, file_name: str, dir_path: str, sub_dir: str = None, do_overwrite: bool = True) -> str:
    """Store a file.
    Base function to handle relative clembench directory paths.
    Args:
        data: Content to store in the file.
        file_name: Name of the file to store.
        dir_path: Path to the directory to store the file to.
        sub_dir: Optional subdirectories to store the file in.
        do_overwrite: Determines if existing file should be overwritten. Default: True
    Returns:
        The path to the stored file.
    """
    if sub_dir:
        dir_path = os.path.join(dir_path, sub_dir)

    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    fp = os.path.join(dir_path, file_name)
    if not do_overwrite:
        if os.path.exists(fp):
            raise FileExistsError(fp)

    with open(fp, "w", encoding='utf-8') as f:
        if file_name.endswith(".json"):
            json.dump(data, f, ensure_ascii=False)
        else:
            f.write(data)
    return fp
