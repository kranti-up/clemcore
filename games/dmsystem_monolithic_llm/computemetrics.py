from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from clemgame import get_logger


logger = get_logger(__name__)


class ComputeMetrics:
    def __init__(self):
        pass

    def _setto_lower(self, slots: dict) -> dict:
        return {
            (key.lower() if isinstance(key, str) else key): 
            (value.lower() if isinstance(value, str) else value) 
            for key, value in slots.items()
        }

    def run(self, results):
        if not "slots_gt" in results or not "slots_gen" in results:
            logger.error(f"Slots not found in the results: {results}")
            return None
        
        slots_gt = results["slots_gt"]
        slots_gen = results["slots_gen"]
        slots_cat = results["cat_slots"]
        slots_noncat = results["noncat_slots"]

        if slots_gt is None or slots_gen is None or slots_cat is None:
            logger.error(f"Slots for game slots_gt: {slots_gt} slots_gen: {slots_gen} slots_cat: {slots_cat} are None")
            return 0, 0, None
        
        
        self._setto_lower(slots_gen)


        accuracy = 0
        if slots_cat == list(slots_gen.keys()) or set(slots_cat).issubset(set(slots_gen.keys())):
            missed_values = []
            for key in slots_cat:
                if slots_gt[key] != slots_gen[key]:
                    missed_values.append({key: {"gt": slots_gt[key], "gen": slots_gen[key]}})

            if missed_values:
                logger.error(f"Values of the ground truth slots and generated slots do not match {missed_values}")
                return 0, round(len(missed_values)/len(slots_cat), 2), missed_values
            
            accuracy = 1
            return accuracy, 0, None

        else:
            missed_keys = list(set(slots_cat) - set(slots_gen.keys()))
            logger.error(f"Keys of the ground truth slots and generated slots do not match {missed_keys}")
            return 0, 0, missed_keys       


