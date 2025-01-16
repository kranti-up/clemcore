import clemgame
from clemgame import get_logger

logger = get_logger(__name__)

class GameValidator:
    def __init__(self, game_name: str, gt_slots: dict, cat_slots: list, noncat_slots: list):
        self.game_name = game_name
        self.gt_slots = gt_slots
        self.cat_slots = cat_slots
        self.noncat_slots = noncat_slots
  
    def _setto_lower(self, slots: dict) -> dict:
        return {
            str(key).lower(): str(value).lower()
            for key, value in slots.items()
        }

    def run(self, gen_slots: dict) -> bool:
        logger.info(f"Validating slots for game {self.game_name}")
        logger.info(f"Ground truth slots: {self.gt_slots}")
        logger.info(f"Generated slots: {gen_slots}")

        if self.gt_slots is None or gen_slots is None:
            logger.error(f"self.gt_slots: {self.gt_slots} gen_slots: {gen_slots}")
            return False, list(self.gt_slots.keys())
        
        #Set GT slots and values to lowercase, if they are strings
        self.gt_slots = self._setto_lower(self.gt_slots)
        gen_slots = self._setto_lower(gen_slots)

        #Compare the keys and values of the two dictionaries
        missed_keys = []
        missed_values = []
        for key, value in self.gt_slots.items():
            if key not in gen_slots.keys():
                missed_keys.append(key)

            if value != gen_slots[key]:
                missed_values.append({key: {"gt": value, "gen": gen_slots[key]}})

        if missed_keys:
            logger.error(f"Keys of the ground truth slots and generated slots do not match {missed_keys}")
            return False, missed_keys
        
        if missed_values:
            logger.error(f"Values of the ground truth slots and generated slots do not match {missed_values}")
            return False, missed_values
        
        return True, None

        #if self.gt_slots.keys() != gen_slots.keys():
        '''
        if self.cat_slots == list(gen_slots.keys()) or set(self.cat_slots).issubset(set(gen_slots.keys())):
            missed_values = []
            for key in self.cat_slots:
                if self.gt_slots[key] != gen_slots[key]:
                    missed_values.append({key: {"gt": self.gt_slots[key], "gen": gen_slots[key]}})

            if missed_values:
                logger.error(f"Values of the ground truth slots and generated slots do not match {missed_values}")
                return False, missed_values
            
            return True, None

        else:
            missed_keys = list(set(self.cat_slots) - set(gen_slots.keys()))
            logger.error(f"Keys of the ground truth slots and generated slots do not match {missed_keys}")
            return False, missed_keys
        '''

if __name__ == "__main__":
    game_name = "llm-monolithic"
    '''
    gt_slots = {"area": "centre", "bookday": "friday", "bookpeople": "4", "booktime": "14:15", "food": "chinese", "name": "charlie chan", "pricerange": "cheap"}
    cat_slots = ["pricerange", "area", "bookday", "bookpeople"]
    noncat_slots = ["food", "name", "booktime", "address", "phone", "postcode", "ref"]
    gt_slots = {"arriveby": "17:45", "day": "thursday", "departure": "cambridge", "destination": "leicester"}
    cat_slots = ["departure", "day", "destination"]
    noncat_slots = [
              "arriveby",
              "bookpeople",
              "leaveat",
              "trainid",
              "ref",
              "price",
              "duration"
            ]
    '''
    gt_slots = {"area": "centre", "bookday": "thursday", "bookpeople": "7", "booktime": "10:30", "food": "italian", "name": "stazione restaurant and coffee bar", "pricerange": "expensive"}
    cat_slots = ["area"]
    noncat_slots = [
              "pricerange",
              "food",
              "name",
              "bookday",
              "bookpeople",
              "booktime",
              "address",
              "phone",
              "postcode",
              "ref"
            ]
    gvd = GameValidator(game_name, gt_slots, cat_slots, noncat_slots)
    '''
    gen_slots = {}# {"area": "centre", "bookday": "Friday", "bookpeople": 4, "booktime": "14:15", "food": "chinese", "name": "Charlie Chan", "pricerange": "cheap"}
    gen_slots = {"trainID": "TR5465", "departure_location": "Cambridge", "arrival_location": "Leicester", 
                 "date": "Thursday", "leaveAt": "15:21", "arriveBy": "17:06", "price": "37.80 pounds",
                   "day": "Thursday", "departure": "Cambridge", "destination": "Leicester", "arriveby": "17:06"}
    '''
    gen_slots = {"restaurant_name": "Stazione Restaurant and Coffee Bar", "area": "centre", "bookday": "Thursday", "booktime": "10:30", "bookpeople": 7, "food": "italian", "pricerange": "expensive", "name": "Stazione Restaurant and Coffee Bar"}
    status, misses = gvd.run(gen_slots)
    print(status, misses)
