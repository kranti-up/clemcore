import json
import clemgame
from clemgame import file_utils


logger = clemgame.get_logger(__name__)
GAME_NAME = "detectobject"

class PrepareWorldData:
    def __init__(self, filename):
        self.filename = f"resources/data/{filename}"
        self.prepareworldinfo()


    def prepareworldinfo(self):
        self.worldinfo = file_utils.load_json(f"{self.filename}", GAME_NAME)

    def getworldinfo(self, objectname):
        if objectname in self.worldinfo:
            return self.worldinfo[objectname]
        else:
            print(f"Object {objectname} not found.")
            raise ValueError(f"Object {objectname} not found.")
            return None


if __name__ == "__main__":
    pwd = PrepareWorldData("fashion_prefab_metadata_all.json")
    print(pwd.getworldinfo("1514019/Rearranged/Jeans_Grey"))