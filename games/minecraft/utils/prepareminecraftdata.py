from clemgame import file_utils
from games.minecraft.utils.minecraftdata import MineCraftData


GAME_NAME = 'minecraft'

mcd = MineCraftData()
game_ids = mcd.next_game_dialogue_with_code("val")

dialogues_dict = {}
for index, game_id in enumerate(game_ids):
    dialogues_dict[game_id] = {}
    dialogue = mcd.get_random_dialogue_with_code('val', game_id)
    for index, turn in enumerate(dialogue):
        d = ". ".join(turn[0])
        a = turn[1]
        dialogues_dict[game_id][index+1] = {"utterance": d, "action": a}


file_utils.store_game_file(dialogues_dict, "minecraft_dialogues.json", GAME_NAME, "resources/")