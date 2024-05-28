import os
import random

from clemgame import file_utils

GAME_NAME = 'minecraft'

class MineCraftData:
    def __init__(self):
        self.data_dir = '/home/admin/Desktop/codebase/cocobots/detectobject_code/clembench/games/minecraft/resources/data/'
        self.process()
        self.extract_context_actions()
        self.convert_action_to_code()
        self.compute_num_turns_dialogs()

    def read_file(self, filename):
        try:
            with open(filename) as f:
                return f.readlines()
        except FileNotFoundError:
            raise FileNotFoundError


    def read_games_from_dialogue(self, dialogue):
        game = []
        #Reads each game from dialogue
        name = dialogue[0]
        for d in dialogue[1:]:
            game.append(d.strip())
        return name, game

    def extract_paths_ids_dialogs(self, folder, file_path, file_name):

        if 'train' in folder:
            games_path = self.games_path['train']
            games_ids = self.games_ids['train']
            games_dialogs = self.games_dialogs['train']
        elif 'val' in folder:
            games_path = self.games_path['val']
            games_ids = self.games_ids['val']
            games_dialogs = self.games_dialogs['val']
        else:
            games_path = self.games_path['test']
            games_ids = self.games_ids['test']
            games_dialogs = self.games_dialogs['test']

        games_path.append(file_path)
        games_ids.append(file_name.split('.')[0])

        dialog = self.read_file(file_path)
        name = dialog[0].strip()
        if name not in games_dialogs:
            games_dialogs[name] = dialog[1:]

    def process(self):
        self.games_path = {'train':[], 'val': [], 'test': []}
        self.games_ids = {'train':[], 'val': [], 'test': []}
        self.games_dialogs = {'train':{}, 'val': {}, 'test': {}}
        print('Processing MineCraft Data')
        #Iterate through folders
        for folder in os.listdir(self.data_dir):
            folder_path = os.path.join(self.data_dir, folder)
            if folder.startswith('.') and os.path.isfile(folder_path):
                continue
            #Iterate through files
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                
                if file_name.startswith('.'):
                    continue
                self.extract_paths_ids_dialogs(folder, file_path, file_name)

    def compute_num_turns_dialogs(self, skip_game_type = []):
        self.game_turns = {}

        for game_type in self.game_dialog_code:
            if game_type in skip_game_type:
                continue
            self.game_turns[game_type] = {}
            for game in self.game_dialog_code[game_type]:
                self.game_turns[game_type][game] = len(self.game_dialog_code[game_type][game])
            self.game_turns[game_type] = sorted(self.game_turns[game_type].items(), key=lambda item: item[1])
            self.game_turns[game_type] = {k: v for k, v in self.game_turns[game_type]}

    def get_num_turns_game_id(self, game_id):
        if game_id in self.game_turns['train']:
            return self.game_turns['train'][game_id]
        elif game_id in self.game_turns['val']:
            return self.game_turns['val'][game_id]
        elif game_id in self.game_turns['test']:
            return self.game_turns['test'][game_id]
        else:
            return -1

    def get_games_files_path(self, game_type='val'):
        return self.games_path[game_type]

    def get_games_ids(self, game_type='val'):
        return self.games_dialogs[game_type]

    def get_games_stats(self):

        train_games_len = len(self.games_dialogs['train'])
        val_games_len = len(self.games_dialogs['val'])
        test_games_len = len(self.games_dialogs['test'])
        print('Train Games: ', train_games_len)
        print('Val Games: ', val_games_len)
        print('Test Games: ', test_games_len)
        print('Total Games = ', train_games_len + val_games_len + test_games_len)

    def get_dialogue_for_game_id(self, game_id):
        if game_id in self.games_dialogs['train']:
            return self.games_dialogs['train'][game_id]

        elif game_id in self.games_dialogs['val']:
            return self.games_dialogs['val'][game_id]

        elif game_id in self.games_dialogs['test']:
            return self.games_dialogs['test'][game_id]

        return None

    def get_context_action(self, dialog):
        dialogue_context_action = []
        action = []
        context = []
        for d in dialog:
            if(d[0] != '['):
                if action:
                    dialogue_context_action.append((context, action))
                    context = []
                    action = []
                context.append(d)
            else:
                action.append(d)
        if context or action:
            dialogue_context_action.append((context, action))

        return dialogue_context_action

    def extract_context_actions(self, skip_game_type = []):
        self.game_dialog_actions = {}
        print('Extracting Dialogues, Actions')
        for game_type in self.games_dialogs:
            if game_type in skip_game_type:
                continue
            dialogues = self.games_dialogs[game_type]
            for game_id in dialogues:
                #print(dialogues[game_id])
                if game_type not in self.game_dialog_actions:
                    self.game_dialog_actions[game_type] = {game_id:self.get_context_action(dialogues[game_id])}
                else:
                    self.game_dialog_actions[game_type][game_id] = self.get_context_action(dialogues[game_id])

    def get_code(self, utterance):
        data = utterance.split(" ")
        #The following split works only if the MineCraft data has the following format
        # Builder puts down a purple block at X:1 Y:1 Z:0
        # Builder picks up a blue block at X:0 Y:2 Z:0
        color = data[4]
        x = data[7].split(':')[1]
        y = data[8].split(':')[1]
        z = data[9].split(':')[1].split(']')[0]
        if 'puts' in utterance:
            command = 'place'
        elif 'picks' in utterance:
            command = 'pick'
        else:
            return

        command = command + '(' + 'color' + '=' + "'" + color + "'" + ',' + 'x=' + x + ',' + 'y=' + y + ',' + 'z=' + z + ')'
        return command

    def convert_action_to_code(self, skip_game_type = []):
        self.game_dialog_code = {}
        print('Converting Actions to Code')
        for game_type in self.game_dialog_actions:

            if game_type in skip_game_type:
                continue

            for id in self.game_dialog_actions[game_type]:
                for diag, actions in self.game_dialog_actions[game_type][id]:
                    codes = []
                    for act in actions:
                        code = self.get_code(act)
                        if not code:
                            print('Failure in converting action to code: ', act, id)
                            continue
                        codes.append(code)
                    if game_type not in self.game_dialog_code:
                        self.game_dialog_code[game_type] = {id: [(diag, codes)]}
                    else:
                        if id not in self.game_dialog_code[game_type]:
                            self.game_dialog_code[game_type][id] = [(diag, codes)]
                        else:
                            self.game_dialog_code[game_type][id].append((diag, codes))
        return self.game_dialog_code


    def strip_anchors_from_dialogue(self, dialogue_action_list):
        dialogue_stripped = []
        for diag_act in dialogue_action_list:
            d_list, a_list = diag_act
            if d_list and a_list:
                diag_text = []
                for d in d_list:
                    text_only = d.split('>')[1].strip()
                    diag_text.append(text_only)

                dialogue_stripped.append((diag_text, a_list))
            else:
                continue
        return dialogue_stripped


    def get_random_dialogue_with_code(self, game_type='val', game_id=None):
        #print(self.games_dialogs[game_type])
        if not game_id:
            game_id = random.choice(list(self.game_dialog_code[game_type].keys()))

        return self.strip_anchors_from_dialogue(self.game_dialog_code[game_type][game_id])


    def next_game_dialogue_with_code(self, game_type='val'):
        #games_ids = self.games_dialogs[game_type]
        games_ids = self.game_turns[game_type]
        #Generator to spit game_ids one by one
        for game in games_ids:
            yield game

    def get_all_dialog_turns(self, game_type='val'):
        self.turn_dialog_all = []
        game_ids = self.next_game_dialogue_with_code(game_type)
        for game_id in game_ids:
            dialogue = self.get_random_dialogue_with_code(game_type, game_id)
            for diag, act in dialogue:
                diag = ' '.join(diag)
                self.turn_dialog_all.append({diag:act})
        return self.turn_dialog_all