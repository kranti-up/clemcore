import json

import clemgame
from clemgame import file_utils


logger = clemgame.get_logger(__name__)
GAME_NAME = "detectobject"

class ProcessDialogueData:
    def __init__(self, filename):
        self.filename = f"resources/data/{filename}"


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


    def run(self):
        self.clemtestdata = []
        missing_annotations = []
        dialogues = file_utils.load_json(self.filename, GAME_NAME)
        dialogue_data = dialogues["dialogue_data"]
        for dialogue_index, dialogue in enumerate(dialogue_data):
            clemdialogue = []
            testdialogue = {"uapairs": []}
            testdialogue["scene_ids"] = dialogue["scene_ids"]
            scenedata = self.preparesceneinfo(testdialogue["scene_ids"])
            for turn in dialogue["dialogue"]:
                if "system_transcript_annotated" not in turn:
                    missing_annotations.append((dialogue_index, turn['turn_idx'], turn['transcript'], turn['system_transcript']))
                    continue

                testdialogue["uapairs"].append((turn["transcript"], turn["system_transcript"]))

                objects = turn["system_transcript_annotated"]["act_attributes"]["objects"]
                if objects:
                    testdialogue["groundtruth"] = objects
                    testdialogue["details"] = self.getsceneinfo(scenedata, objects)
                    clemdialogue.append(testdialogue.copy())
                    testdialogue["uapairs"] = []
                    testdialogue["groundtruth"] = []
            self.clemtestdata.append(clemdialogue)
  
        if missing_annotations:
            print("Missing annotations:")
            for ma in missing_annotations:
                print(ma)

        file_utils.store_game_file(self.clemtestdata, "clemtestdata.json", GAME_NAME, "resources/data/")



if __name__ == "__main__":
    pdd = ProcessDialogueData("simmc2.1_dials_dstc11_mini.json")
    pdd.run()