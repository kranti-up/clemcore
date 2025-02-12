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

## TODOs:
* update test_benchmark.py (contains old versions of parameters and experiment names)
* update documentation
* update remaining games
* present instructions for upgrading at next clemclub meeting

## Preparational Thoughts
### Adding a new game
* implement game based on [template](#game-template)
* add entry in game registry specifying at least game_name, game_path, and game_description

## Game Registry Fields:

```
{
"game_name": mandatory, game identifier, should be the same as GAME_NAME in master.py to avoid confusion (as the latter will be used for the results dierctory) (should we add a check?)
"game_path": mandatory, path to game  # absolute or relative to clemgame directory
"description": "A brief description of the game"
"main_game": "main game identifier" # to cluster different versions of the same game
"player": "single" | "two" | "multi"
"image": "none" | "single" | "multi"
"languages": ["en"] # list of ISO codes
"benchmark": ["X.X", "Y.Y"] # lists all benchmark versions in which this game was used 

# The games that are part of a specific collection can be filtered based on the 
# game attributes.
# For reproducibility, benchmark will also list all benchmark versions a game has   
# been used in previously.

# Could also contain optional instance file or list of experiments, see 
# discussion [here](https://github.com/clp-research/clemgames/issues/3)}
```

### Game Structure
```
game
    in # directory containing instances_LANG_VERSION.json
    resources
        lang (optional)
            other resources
            initial_prompts
    .gitignore # optional game specific ignore
    __init__.py # empty file to make game a module (for automatically creating docs)
    instancegenerator.py # script reading in resources and generating instance file(s)
    master.py # script defining game properties (can also be defined in separate files) and game master
    requirements.txt # optional game specific requirements
```

### Results Structure
built by GameMaster and GameScorer, main path specified as argument in cli.py and then built by adding model and experiment sub-directories, no changes needed

### possible game collections
* benchmark versions (currently different versions of code and instances, in the future only different instances)
  * text based benchmark (see clembench paper)
  * multimodal benchmark (see current version of the multimodal paper)
* game class (several versions of one game, for in-depth analysis)
* language-specific version (specific games or collection for a specific language)

