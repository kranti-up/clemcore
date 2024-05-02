import json

import clemgame
from clemgame import file_utils


logger = clemgame.get_logger(__name__)
GAME_NAME = "detectobject"

class ProcessCoRefData:
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
            skip_turn = False
            for index, turn in enumerate(dialogue["dialogue"]):
                if skip_turn:
                    continue    


if __name__ == "__main__":
    #pdd = ProcessDialogueData("simmc2.1_dials_dstc11_mini.json")
    pdd = ProcessCoRefData("coref-pred-devtest-mini.json", False)
    pdd.run(save_file_name="clemtestdata_wocr.json")