import json

import clemgame
from clemgame import file_utils


logger = clemgame.get_logger(__name__)
GAME_NAME = "detectobject"

class ProcessDialogueData:
    def __init__(self, filename, use_cr=True):
        self.filename = f"resources/data/{filename}"
        self.use_cr = use_cr


    def getsceneinfo(self, scenedata, objects):
        objinfo = {}
        for obj in objects:
            for sceneid, sceneinfo in scenedata.items():
                for scenes, scenesvalue in sceneinfo.items():
                    for scenesval in scenesvalue:
                        for sceneobject in scenesval["objects"]:
                            if sceneobject['index'] == obj:
                                objinfo[obj] = sceneobject
        return objinfo


    def preparesceneinfo(self, scenelist):
        scenedata = {}
        for sceneid, filename in scenelist.items():
            info = file_utils.load_json(f"resources/data/public/{filename}_scene.json", GAME_NAME)
            scenedata[sceneid] = info
        return scenedata


    def run(self, save_file_name="clemtestdata.json"):
        self.clemtestdata = []
        missing_annotations = []
        dialogues = file_utils.load_json(self.filename, GAME_NAME)
        dialogue_data = dialogues["dialogue_data"]
        for dialogue_index, dialogue in enumerate(dialogue_data):
            clemdialogue = []
            testdialogue = {"uapairs": []}
            testdialogue["scene_ids"] = dialogue["scene_ids"]
            scenedata = self.preparesceneinfo(testdialogue["scene_ids"])
            skip_next_turn = False
            for index, turn in enumerate(dialogue["dialogue"]):
                if skip_next_turn:
                    skip_next_turn = False
                    continue

                if "system_transcript_annotated" not in turn:
                    missing_annotations.append((dialogue_index, turn['turn_idx'], turn['transcript'], turn['system_transcript']))
                    continue

                if not turn["transcript_annotated"]["disambiguation_label"]:
                    testdialogue["uapairs"].append((turn["transcript"], turn["system_transcript"]))
                    #If the prev turn is ambiguous, it should not be overwritten
                    if "disambiguation_label" not in testdialogue:
                        testdialogue["disambiguation_label"] = 0
                    system_turn_to_use = turn


                else:
                    if self.use_cr:
                        testdialogue["uapairs"].append((turn["transcript"], turn["system_transcript"]))
                        testdialogue["disambiguation_label"] = 1
                        system_turn_to_use = turn

                    else:
                        if index + 1 < len(dialogue["dialogue"]):
                            current_user_utterance = turn["transcript"]
                            next_system_utterance = dialogue["dialogue"][index + 1]["system_transcript"]
                            testdialogue["uapairs"].append((current_user_utterance, next_system_utterance))
                            system_turn_to_use = dialogue["dialogue"][index + 1]
                            testdialogue["disambiguation_label"] = 1
                            skip_next_turn = True
                        else:
                            system_turn_to_use = None

                if system_turn_to_use is None:
                    continue

                objects = system_turn_to_use["system_transcript_annotated"]["act_attributes"]["objects"]
                if objects:
                    testdialogue["groundtruth"] = objects
                    testdialogue["details"] = self.getsceneinfo(scenedata, objects)
                    clemdialogue.append(testdialogue.copy())
                    testdialogue["uapairs"] = []
                    testdialogue["groundtruth"] = []      
                    testdialogue["disambiguation_label"] = 0       

            if testdialogue:
                objects = system_turn_to_use["system_transcript_annotated"]["act_attributes"]["objects"]
                if objects:
                    testdialogue["groundtruth"] = objects
                    testdialogue["details"] = self.getsceneinfo(scenedata, objects)
                else:
                    testdialogue["groundtruth"] = []                    
                    testdialogue["details"] = None

                clemdialogue.append(testdialogue.copy())
                testdialogue["uapairs"] = []
                testdialogue["groundtruth"] = []      
                testdialogue["disambiguation_label"] = 0     
                

            self.clemtestdata.append(clemdialogue)
  
        if missing_annotations:
            print("Missing annotations:")
            for ma in missing_annotations:
                print(ma)


        print(f"Saving {save_file_name}")
        file_utils.store_game_file(self.clemtestdata, save_file_name, GAME_NAME, "resources/data/")



if __name__ == "__main__":
    #pdd = ProcessDialogueData("simmc2.1_dials_dstc11_mini.json")
    pdd = ProcessDialogueData("simmc2.1_dials_dstc11_devtest.json", True)
    pdd.run(save_file_name="clemtestdata_withcr_new.json")