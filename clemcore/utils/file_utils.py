"""
Defines locations within the project structure (for root directories, games and results)
and supplies several functions for loading and storing files
"""

from typing import Dict
import os
import json
import csv

######### path construction functions ###################


def project_root():
    """
        returns absolute path to main directory (clembench)
    """
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def clemcore_root():
    """
        returns absolute path to clemcore directory (clembench/clemcore)
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def results_root(results_dir: str) -> str:
    if os.path.isabs(results_dir):
        return results_dir
    # if not absolute, results_dir is given relative to project root (see default in cli.py)
    return os.path.normpath(os.path.join(project_root(), results_dir))


def game_results_dir(results_dir: str, dialogue_pair: str, game_name: str):
    return os.path.join(results_root(results_dir), dialogue_pair, game_name)


def file_path(file_name: str, game_path: str = None) -> str:
    """
    Get absolute path to a specific file
    TODO check if this is actually ever called without a game_path
    Args:
        file_name: the path to a file (can be a path relative to the game directory)
        game_path: the path to the game directory (optinal)

    Returns: The absolute path to a file relative to the game directory (if specified) or the clembench directory

    """
    if game_path:
        if os.path.isabs(game_path):
            return os.path.join(game_path, file_name)
        else:
            return os.path.join(project_root(), game_path, file_name)
    return os.path.join(project_root(), file_name)


########### file loading functions #########################


def load_csv(file_name: str, game_path: str):
    # iso8859_2 was required for opening nytcrosswords.csv for clues in wordle
    rows = []
    fp = file_path(file_name, game_path)
    with open(fp, encoding='iso8859_2') as csv_file:
        data = csv.reader(csv_file, delimiter=',')
        # header = next(data)
        for row in data:
            rows.append(row)
    return rows


def load_json(file_name: str, game_path: str) -> Dict:
    data = load_file(file_name, game_path, file_ending=".json")
    data = json.loads(data)
    return data


def load_template(file_name: str, game_path: str) -> str:
    # TODO this a bit redundant and could be removed by changing all usages
    #  of load_template (and GameResourceLocator.load_template()) to directly use load_file(..., file_ending=".template")
    return load_file(file_name, game_path, file_ending=".template")


def load_file(file_name: str, game_path: str = None, file_ending: str = None) -> str:
    if file_ending and not file_name.endswith(file_ending):
        file_name = file_name + file_ending
    fp = file_path(file_name, game_path)
    with open(fp, encoding='utf8') as f:
        data = f.read()
    return data


def load_results_json(file_name: str, results_dir: str, dialogue_pair: str, game_name: str) -> Dict:
    file_ending = ".json"
    if not file_name.endswith(file_ending):
        file_name = file_name + file_ending
    fp = os.path.join(game_results_dir(results_dir, dialogue_pair, game_name), file_name)
    with open(fp, encoding='utf8') as f:
        data = f.read()
    data = json.loads(data)
    return data

########### file storing function ################


def store_file(data, file_name: str, dir_path: str, sub_dir: str = None, do_overwrite: bool = True) -> str:
    """
    :param data: to store
    :param file_name: of the file to store
    :param dir_path: to the directory to store to
    :param sub_dir: optional subdirectories
    :param do_overwrite: default: True
    :return: the file path
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
