import clemgame
from clemgame import get_logger

from fuzzywuzzy import process

logger = get_logger(__name__)

class GameValidator:
    def __init__(self, game_name: str, gt_slots: dict):
        self.game_name = game_name
        self.gt_slots_info, self.gt_slots_book = self._processgtslots(gt_slots)
  
    def _setto_lower(self, slots: dict) -> dict:
        return {
                str(domain).lower(): {str(key).lower(): str(value).lower() for key, value in dvalue.items()}
                for domain, dvalue in slots.items()
            }
    
    def _processgtslots(self, slots: dict):
        infoslots = {}
        bookslots = {}

        for domain, dvalue in slots.items():
            infoslots[domain] = {}
            bookslots[domain] = {}
            for key, kvalue in dvalue.items():
                if key == "info":
                    for k, v in kvalue.items():
                        infoslots[domain][k] = v

                elif key == "book":
                    for k, v in kvalue.items():
                        if k == "invalid":
                            continue
                        bookslots[domain][f"book{k}"] = v
                else:
                    continue

        return infoslots, bookslots
    
    def _processgenslots(gen_slots: dict) -> dict:
        modgen_slots = {}
        for key, data in gen_slots.items():
            if key == "train":
                if key not in modgen_slots:
                    modgen_slots[key] = {}
                for k, v in data.items():
                    if k == "tickets":
                        modgen_slots[key]["bookpeople"] = v
                    else:
                        modgen_slots[key][k] = v
            elif key == "restaurant":
                if key not in modgen_slots:
                    modgen_slots[key] = {}

                for k, v in data.items():
                    if k == "people":
                        modgen_slots[key]["bookpeople"] = v
                    elif k == "time":
                        modgen_slots[key]["booktime"] = v
                    elif k == "day":
                        modgen_slots[key]["bookday"] = v
                    else:
                        modgen_slots[key][k] = v
            elif key == "hotel":
                if key not in modgen_slots:
                    modgen_slots[key] = {}

                for k, v in data.items():
                    if k == "people":
                        modgen_slots[key]["bookpeople"] = v
                    elif k == "stay":
                        modgen_slots[key]["bookstay"] = v
                    elif k == "day":
                        modgen_slots[key]["bookday"] = v
            else:
                modgen_slots[key] = data

        return modgen_slots    
    

    def _compare_slots(self, gt_slots: dict, gen_slots: dict):
        gtcompslots = self._setto_lower(self.gt_slots_info)
        gencompslots = self._setto_lower(gen_slots)
        print(gtcompslots)
        print(gencompslots)

        missed_domains = [domain for domain in gtcompslots if domain not in gencompslots]
        if missed_domains:
            logger.error(f"Domains of the ground truth slots and generated do not match {missed_domains}")
            return False, missed_domains

        missed_values = []
        for domain, dvalue in gtcompslots.items():
            missed_keys = [key for key in dvalue if key not in gencompslots[domain]]
            if missed_keys:
                logger.error(f"Keys of the ground truth slots and generated slots do not match {missed_keys}")
                return False, [{domain:missed_keys}]
            
            mvalues = [
                {key: {"gt": value, "gen": gencompslots[domain][key]}}
                for key, value in dvalue.items()
                if value != gencompslots[domain][key]
            ]
            if mvalues:
                missed_values.append({domain: mvalues})

        if missed_values:
            logger.error(f"Values of the ground truth slots and generated slots do not match {missed_values}")
            return False, missed_values                      
        
        return True, None

    def run(self, gen_slots: dict) -> bool:
        logger.info(f"Validating slots for game {self.game_name}")
        logger.info(f"Ground truth slots: info: {self.gt_slots_info}, book: {self.gt_slots_book}")
        logger.info(f"Generated slots: {gen_slots}")

        if not self.gt_slots_info or not gen_slots:
            logger.error(f"self.gt_slots: {self.gt_slots_info} gen_slots: {gen_slots}")
            return False, list(self.gt_slots_info.keys())
        
        modgen_slots = self._processgenslots(gen_slots)

        status, misses = self._compare_slots(self.gt_slots_info, modgen_slots)
        if not status:
            return status, misses
        
        status, misses = self._compare_slots(self.gt_slots_book, modgen_slots)
        if not status:
            return status, misses
        
        return True, None
        


if __name__ == "__main__":
    game_name = "llm-monolithic"

    gt_slots = {
              "taxi": {
                "info": { "arriveBy": "15:00" },
                "reqt": ["car type", "phone"],
                "fail_info": {}
              },
              "attraction": {
                "info": { "area": "east" },
                "reqt": ["entrance fee"],
                "fail_info": { "area": "west" }
              },
              "restaurant": {
                "info": { "name": "nandos" },
                "fail_info": { "name": "travellers rest" },
                "book": {
                  "people": "6",
                  "day": "monday",
                  "invalid": False,
                  "time": "15:00"
                },
                "fail_book": {}
              }
            } 
    gen_slots = {
              "taxi": {"arriveBy": "15:00"},
              "attraction": {"area": "east"},
              "restaurant": {"name": "nandos", "bookpeople": "2", "bookday": "monday", "booktime": "15:00"},
            }    
    gvd = GameValidator(game_name, gt_slots)
    status, misses = gvd.run(gen_slots)
    print(status, misses)

