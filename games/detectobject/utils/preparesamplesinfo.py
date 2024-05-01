import json


from games.detectobject.utils.prepareworlddata import PrepareWorldData


class PrepareSampels:
    def __init__(self, world_filename):
        self.pwd = PrepareWorldData(world_filename)

    def getobjectids(self, dialogue):
        all_object_ids = {}
        for turn in dialogue:
            for objid in turn["groundtruth"]:
                all_object_ids[objid] = turn["details"][str(objid)]

        return all_object_ids

    def convert_to_text(self, worldinfo):
        world_info_text = "object_id, object_type, object_color, object_size\n"
        for objid, objtype, objcolor, objsize in worldinfo:
            world_info_text += f"{objid}, {objtype}, {objcolor}, {objsize}\n"
        return world_info_text
    
    def getdialogue_scene(self, dialogue):
        all_object_ids = self.getobjectids(dialogue)
        world_info = []
        for objid, objdetails in all_object_ids.items():
            try:
                objinfo = self.pwd.getworldinfo(objdetails["prefab_path"])
            except ValueError as e:
                print(e, objdetails)
                continue

            if "size" in objinfo:
                world_info.append((objid, objinfo["type"], objinfo["color"], objinfo["size"]))
            else:
                #furniture data
                world_info.append((objid, objinfo["type"], objinfo["color"], "NA"))


        world_info = self.convert_to_text(world_info)
        return world_info
    
    def format_dialogue(self, dialogue):
        for turn in dialogue:
            for index, uapair in enumerate(turn["uapairs"]):
                uapair[0] = "User: " + uapair[0]
                uapair[1] = "System: " + uapair[1]

    def getdisambiguationlabel(self, dialogue):
        for turn in dialogue:
            if turn["disambiguation_label"]:
                return 1
        return 0