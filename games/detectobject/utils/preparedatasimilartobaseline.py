import re

import clemgame
from clemgame import file_utils


logger = clemgame.get_logger(__name__)
GAME_NAME = "detectobject"


class PrepareDataAsBaseline:
    def __init__(self, filename, use_cr=True, use_dh_all=True):
        self.filename = f"resources/data/{filename}"
        self.use_cr = use_cr
        self.use_dh_all = use_dh_all
        self.tag_property = ['sleeve', 'sleeved', 'hanging', 'hangs', 'rating', 'fluffy', 'without the arms', 'taller', 'sleeveless', 'christmas', 'Christmas-looking']
        self.tag_previous = ['mentioned', 'earlier', 'discussing', 'discussed', 'you put', 'pointed out', 'showed', 'just talking', 'just added', 'just bought', 'was just', 'just told', 'you recommended', 'was asking', 'added', 'before', 'shown', 'you just', 'my cart', 'last', 'previously', 'you suggested', 're(?!not) talking', 'just asked', 'you told', 'you found', 'were just', 'you are recommending', 'first thing i looked at', '.*ed .* first']
        self.tag_confirmation = ['okay', 'yeah', 'ok([^a-zA-Z]|$)', 'yes', 'both', 'precisely', 'yep', 'Yep!', 'I do!']
        self.tag_item = ['jacket', 'blouse', 'shirt', 'jean', 'pants', 'coat', 'sweater', 'tee', 'dress', 'skirt', 'shorts', '[^a-zA-Z]hat([^a-zA-Z]|$)', 'hoodie', 'chair', 'sofa', 'couch', 'rug']
        self.tag_position = ['right', 'left', 'bottom', 'top', 'middle', 'center', 'leftmost', 'rightmost', 'second', 'cubicle', 'table', 'rack', 'floor', 'lower', 'shelf', 'further', 'above', 'front', 'behind', 'next', 'wall', 'back', 'cubby', 'closet', 'display', 'row', 'wardrobe', 'sides', 'cabinet', 'end', 'windows', 'far', 'corner', 'shelves', 'cabinet', 'end', 'on\s(?!that)', 'closer', 'area', 'farther', 'by the', 'closest']
        self.tag_color = ['gray', 'grey', 'blue', 'red', 'yellow', 'brown', 'black', 'white', 'purple', 'pink', 'green', 'violet', 'olive', 'maroon', 'orange', 'beige', 'gold', 'silver', 'teal', 'wooden', 'camo', 'zebra', 'denim', 'light', 'dark', 'darker', 'lighter']
        self.tags = {'colour': self.tag_color, 'position': self.tag_position, 'item': self.tag_item,
                     'confirmation': self.tag_confirmation, 'previous': self.tag_previous, 'property': self.tag_property }
        self.tags_groups = {'individual_property': [self.tag_color, self.tag_property, self.tag_item],
                           'dialogue_history': [self.tag_previous, self.tag_confirmation],
                           'relational_context': [self.tag_position]}
        
    def count_turns_base_data(self):
        dialogues = file_utils.load_json(self.filename, GAME_NAME)
        dialogue_data = dialogues["dialogue_data"]
        total_turns = 0
        for dialogue_index, dialogue in enumerate(dialogue_data):
            for index, turn in enumerate(dialogue["dialogue"]):
                total_turns += 1
        return total_turns

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
    
    def tag_utterance(self, utterance):
        result_tags = {"individual_property": 0, "dialogue_history": 0, "relational_context": 0}
        for group_name, tags in self.tags_groups.items():
            for tag in tags:
                for item in tag:
                    result = re.search(rf"{item}([\s,s.?]|$)", utterance, re.IGNORECASE)
                    if result:
                        result_tags[group_name] = 1
        return result_tags
    
    def run(self, save_file_name):
        dialogues = file_utils.load_json(self.filename, GAME_NAME)
        dialogue_data = dialogues["dialogue_data"]

        clemtestdata = []
        for dialogue_index, dialogue in enumerate(dialogue_data):
            dialogue_history = []
            prev_turn_cr = False
            objects_from_last_turn = []
            for index, turn in enumerate(dialogue["dialogue"]):
                testdialogue = {}                
                testdialogue["utterance"] = turn["transcript"]
                result_tags = self.tag_utterance(testdialogue["utterance"])
                for group_name, value in result_tags.items():
                    testdialogue[group_name] = value

                testdialogue["groundtruth"] = turn["transcript_annotated"]["act_attributes"]["objects"]
                testdialogue["scene_ids"] = dialogue["scene_ids"]
                scenedata = self.preparesceneinfo(testdialogue["scene_ids"])
                testdialogue["details"] = self.getsceneinfo(scenedata, testdialogue["groundtruth"])                

                if dialogue_history:
                    testdialogue["history"] = dialogue_history.copy()

                    if self.use_dh_all != "all":
                        dialogue_history = []
                else:
                    testdialogue["history"] = []

                if self.use_dh_all != "none":
                    dialogue_history.append((turn["transcript"], turn["system_transcript"]))

                if "disambiguation_label" in turn and turn["disambiguation_label"]:
                    testdialogue["is_cr_turn"] = "before"
                    prev_turn_cr = True
                    objects_from_last_turn = turn["transcript_annotated"]["act_attributes"]["objects"]
                
                else:
                    if prev_turn_cr:
                        prev_turn_cr = False
                        testdialogue["is_cr_turn"] = "after"
                        if objects_from_last_turn != turn["transcript_annotated"]["act_attributes"]["objects"]:
                            raise Exception("Objects from last turn and current turn are different")
                        objects_from_last_turn = []
                    else:
                        testdialogue["is_cr_turn"] = "none"

                clemtestdata.append(testdialogue.copy())


        print(f"Saving {save_file_name}, Total Turns {len(clemtestdata)}")
        file_utils.store_game_file(clemtestdata, save_file_name, GAME_NAME, "resources/data/")


    def run_split(self, save_file_name):
        self.clemtestdata = []
        missing_annotations = []
        dialogues = file_utils.load_json(self.filename, GAME_NAME)
        dialogue_data = dialogues["dialogue_data"]
        skip_next_turn = False
        use_utterance_from_last_turn = ""
        objects_from_last_turn = []
        testdialogue = {}
        dialogue_history = []

        for dialogue_index, dialogue in enumerate(dialogue_data):
            if use_utterance_from_last_turn and not skip_next_turn:
                #Last turn of the previous dialogue was ambiguous
                testdialogue["utterance"] = use_utterance_from_last_turn
                result_tags = self.tag_utterance(testdialogue["utterance"])
                for group_name, value in result_tags.items():
                    testdialogue[group_name] = value

                testdialogue["groundtruth"] = objects_from_last_turn
                if dialogue_history:
                    dialogue_history = dialogue_history[:-1]
                    testdialogue["history"] = dialogue_history.copy()
                else:
                    testdialogue["history"] = []

                self.clemtestdata.append(testdialogue.copy())
            testdialogue = {}
            dialogue_history = []
            objects_from_last_turn = []
            use_utterance_from_last_turn = ""
            skip_next_turn = False

            testdialogue["scene_ids"] = dialogue["scene_ids"]
            scenedata = self.preparesceneinfo(testdialogue["scene_ids"])

            for index, turn in enumerate(dialogue["dialogue"]):
                if skip_next_turn:
                    dialogue_history.append((use_utterance_from_last_turn, turn["system_transcript"]))
                    skip_next_turn = False
                    use_utterance_from_last_turn = ""
                    continue

                if "disambiguation_label" in turn and turn["disambiguation_label"]:
                    testdialogue["disambiguation_label"] = 1
                    testdialogue["is_cr_turn"] = "before"

                    use_utterance_from_last_turn = turn["transcript"]
                                
                    if self.use_cr:
                        skip_next_turn = False
                        dialogue_history.append((turn["transcript"], turn["system_transcript"]))
                        objects_from_last_turn = turn["transcript_annotated"]["act_attributes"]["objects"] 
                    else:
                        skip_next_turn = True
                        testdialogue["utterance"] = turn["transcript"]
                        if objects_from_last_turn:
                            if objects_from_last_turn != turn["transcript_annotated"]["act_attributes"]["objects"]:
                                raise Exception("Objects from last turn and current turn are different")

                        result_tags = self.tag_utterance(testdialogue["utterance"])
                        for group_name, value in result_tags.items():
                            testdialogue[group_name] = value

                        testdialogue["groundtruth"] = turn["transcript_annotated"]["act_attributes"]["objects"]
                        testdialogue["details"] = self.getsceneinfo(scenedata, testdialogue["groundtruth"])
                        if dialogue_history:
                            testdialogue["history"] = dialogue_history.copy()
                            if not self.use_dh_all:
                                dialogue_history = []
                        else:
                            testdialogue["history"] = []

                        

                        self.clemtestdata.append(testdialogue.copy())
                        testdialogue = {}

                else:
                    testdialogue["disambiguation_label"] = 0
                    if "is_cr_turn" in testdialogue and testdialogue["is_cr_turn"]:
                        testdialogue["is_cr_turn"] = "after"
                    else:
                        testdialogue["is_cr_turn"] = "none"

                    testdialogue["utterance"] = turn["transcript"]
                    result_tags = self.tag_utterance(testdialogue["utterance"])
                    for group_name, value in result_tags.items():
                        testdialogue[group_name] = value

                    testdialogue["groundtruth"] = turn["transcript_annotated"]["act_attributes"]["objects"]
                    testdialogue["details"] = self.getsceneinfo(scenedata, testdialogue["groundtruth"])
                    skip_next_turn = False
                    use_utterance_from_last_turn = ""

                    if dialogue_history:
                        testdialogue["history"] = dialogue_history.copy()
                        if not self.use_dh_all:
                            dialogue_history = []
                    else:
                        testdialogue["history"] = []

                    self.clemtestdata.append(testdialogue.copy())
                    testdialogue = {}
                    dialogue_history.append((turn["transcript"], turn["system_transcript"]))



        print(f"Saving {save_file_name}")
        file_utils.store_game_file(self.clemtestdata, save_file_name, GAME_NAME, "resources/data/")


if __name__ == "__main__":
    #pdd = ProcessDialogueData("simmc2.1_dials_dstc11_mini.json")
    pdd = PrepareDataAsBaseline("simmc2_dials_dstc10_devtest.json", False, "all")
    pdd.run(save_file_name="clemtestdata_all_turn_all_dh.json")
    #print(pdd.count_turns_base_data())

