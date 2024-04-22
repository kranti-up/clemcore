import json
import clemgame
from clemgame import file_utils


logger = clemgame.get_logger(__name__)
GAME_NAME = "detectobject"

class PrepareWorldData:
    def __init__(self, filenames):
        self.filename = {}
        for filetype, filename in filenames.items():
            self.filename[filetype] = f"resources/data/{filename}"
        self.prepareworldinfo()


    def prepareworldinfo(self):
        self.worldinfo = {}
        for filetype in self.filename:
            self.worldinfo[filetype] = file_utils.load_json(f"{self.filename[filetype]}", GAME_NAME)

    def getworldinfo(self, objectname):
        for filetype in self.worldinfo:
            if objectname in self.worldinfo[filetype]:
                return self.worldinfo[filetype][objectname]

        print(f"Object {objectname} not found.")
        raise ValueError(f"Object {objectname} not found.")


if __name__ == "__main__":
    pwd = PrepareWorldData({"fashion": "fashion_prefab_metadata_all.json"})
    print(pwd.getworldinfo("1514019/Rearranged/Jeans_Grey"))