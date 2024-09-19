# Preparation for separating games and framework (whereby a benchmark run becomes a framework run with specific games)

## Preamble
### General Questions
* Naming confusion: The class `GameBenchmark` is used for a complete run of all instances of one game (not a set of specific games constituting a benchmark version)
* clemgame could be renamed into framework and framework.py moved to \__init\__.py
* GameMaster vs. DialogueGameMaster: latter extends former/is the separation needed? former used in every game, the latter (additionally) in matchit/mapworld/hellogame/cloudgame/taboo, see example below:
```
class Taboo(DialogueGameMaster):
...

class TabooGameBenchmark(GameBenchmark):
    def create_game_master(self, experiment: Dict, player_models: List[Model]) -> GameMaster:
        return Taboo(experiment, player_models)

```

## TODOs:
* load game_registry in \__init\__.py
* use path from game registry for game loading (currently uses a default location outside the main repository)
* adapt instance file default location to game default location
* update test_benchmark.py (also contains old versions of reference game)

## Preparational Thoughts
### Adding a new game
* implement game based on [template](#game-template)
* add entry in game registry

## Game Registry Fields:

```
{
"game_name": game identifier
"game_path": path to game  # absolute or relative to certain directory(tbd))
"description": "A brief description of the game"
"main_game": "main game identifier"
"player": "single" | "two" | "multi"
"image": "none" | "single" | "multi"
"languages": ["en"] # list of ISO codes
"benchmark": ["vX.X"] # lists all benchmark versions in which this game was used 

# The games that are part of a specific benchmark version are defined in a 
# bash script run_benchmark.sh by listing the identifiers for each game
# but could potentially also be filtered based on the game attributes
# For reproducibility, we could also list all benchmark versions a game has been  
# used in (as in the example above)
}
```

## Isolate Game Template from Framework?
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
|       --> changed to load only specified games/one game at a time as specified in bash script
+--- benchmark.py 
|       list_games() # replaced by pointer to game_registry
+--- clemgame.py
|       load_benchmarks() # rename and adapt based on game registry
|       load_benchmark() # adapted to load game from different location
|       find_benchmark() # integrated into load_benchmark
+--- file_utils.py
|       game_dir() # needs to implement lookup in game_registry
 scripts
|
+--- cli.py # renamed benchmark to framework
|
 tests
|
+--- test_benchmark.py # rename to test_framework.py and adapt
+--- logging.yaml # renamed main logger to framework.run
+--- run_benchmark.sh # added to run a specific set of games constituting a benchmark version
```

