# Preparation for separating games and framework (whereby a benchmark run becomes a framework run with specific games)

## Preamble
### General Questions
* Naming confusion: The class `GameBenchmark` is used for a complete run of all instances of one game (not a set of specific games constituting a benchmark version)
* GameMaster vs. DialogueGameMaster: latter extends former/is the separation needed? former used in every game, the latter (additionally) in matchit/mapworld/hellogame/cloudgame/taboo, see example below:
```
class Taboo(DialogueGameMaster):
...

class TabooGameBenchmark(GameBenchmark):
    def create_game_master(self, experiment: Dict, player_models: List[Model]) -> GameMaster:
        return Taboo(experiment, player_models)

```
* cli.py doesn't throw any errors if game name/model name/instance file doesn't exists. It does show up in clembench.log, but do we want to make this more explicit (at least a "something went wrong, check clembench.log for details" )?

## TODOs:
* update test_benchmark.py (also contains old versions of reference game)

## Preparational Thoughts
### Adding a new game
* implement game based on [template](#game-template)
* add entry in game registry

## Game Registry Fields:

```
{
"game_name": game identifier
"game_path": path to game  # absolte or relative to certain directory(tbd))
"player": single | two | multi
"image": none | single | multi

# The games that are part of a specific benchmark version are defined in a 
# bash script run_benchmark.sh by listing the identifiers for each game
#
# The only problem left is to require a detailed changelog
# in each game directory documenting the different versions, but I think
# we made this a requirement already anyways, right?
}
```

## Isolate Game Template from Framework:
### (Abstract) Classes (clemgame/clemgame.py):
* InstanceGenerator
* Player
* GameMaster (DialogueGameMaster)?
* GameScorer?

### Game Structure
```
game
    in # directory containing instances_LANG_VERSION.json
    resources
        lang (optional)
            other resources
            initial_prompts
    instancegenerator.py # script reading in resources and generating instance file(s)
    game.py (sometimes also just master.py)
    master.py
```

### Results Structure
built by GameMaster and GameScorer, path specified as argument in cli.py, no changes needed

### Benchmark games
* text based benchmark (see clembench paper)
* multimodal benchmark (see current version of the paper)
* other games (student projects, new games, possibly to be added to benchmark)

### Required Changes: 
```
 clemgame
| 
+--- __init__.py 
|       --> change to load only specified games/one game at a time as specified in bash script
+--- benchmark.py 
|       list_games() # replaced by game_registry
+--- clemgame.py
|       load_benchmarks() # rename
|       load_benchmark() # rename
|       find_benchmark() # rename
+--- file_utils.py
|       game_dir() # needs to implement lookup in game_registry
 scripts
|
+--- cli.py #
|
 tests
|
+--- test_benchmark.py # rename to test_framework.py and adapt
|
 run_benchmark.sh # to run a specific set of games constituting a benchmark version
```

