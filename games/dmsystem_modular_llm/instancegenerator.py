from games.dmsystem_monolithic_llm.instancegenerator import DMSystemInstanceGenerator

# set the name of the game in the script, as you named the directory
# this name will be used everywhere, including in the table of results
GAME_NAME = "dmsystem_modular_llm"


if __name__ == "__main__":
    DMSystemInstanceGenerator(GAME_NAME).generate()
