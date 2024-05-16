


class ObjDetectEvaluator:
    def __init__(self):
        pass

    def _compute_fp_fn_tp(self, groundtruth, prediction):
        groundtruth_set = set(groundtruth)
        prediction_set = set(prediction)

        '''
        tp = len(groundtruth_set & prediction_set)  # Intersection: items present in both sets
        fn = len(groundtruth_set - prediction_set)  # Difference: items in groundtruth but not in prediction
        fp = len(prediction_set - groundtruth_set)  # Difference: items in prediction but not in groundtruth

        return {"tp": tp, "fn": fn, "fp": fp}
        '''

        #Following the same logic as the baseline code (https://github.com/facebookresearch/simmc2/blob/main/model/mm_dst/utils/evaluate_dst.py#L306)
        num_correct = len(groundtruth_set & prediction_set)
        num_true = len(groundtruth_set)
        num_pred = len(prediction_set) 

        return {"nc": num_correct, "nt": num_true, "np": num_pred}   
            
    #def _compute_precision_recall_f1(self, tp, fn, fp):
    def _compute_precision_recall_f1(self, nc, nt, np):
        '''
        precision = tp / (tp + fp) if tp + fp > 0 else 0
        recall = tp / (tp + fn) if tp + fn > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0

        return {"precision": precision, "recall": recall, "f1_score": f1}
        '''
        #Following the same logic as the baseline code (https://github.com/facebookresearch/simmc2/blob/main/model/mm_dst/utils/evaluate_dst.py#L360)
        #nc: number of correct predictions
        #nt: number of ground truth labels
        #np: number of predicted labels
        precision = nc / np if np != 0 else 0
        recall = nc / nt if nt != 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0
        f1 = round(f1, 3)

        return {"precision": precision, "recall": recall, "f1_score": f1}
        



    def run(self, results, dialogue_data):
        turnscores, episodescores = {}, {}
        for turn, value in results.items():
            turnscores[int(turn)] = self._compute_fp_fn_tp(value['groundtruth'], value['prediction'])

        for turn, value in turnscores.items():
            '''
            episodescores["tp"] = episodescores.get("tp", 0) + value["tp"]
            episodescores["fn"] = episodescores.get("fn", 0) + value["fn"]
            episodescores["fp"] = episodescores.get("fp", 0) + value["fp"]
            '''
            episodescores["nc"] = episodescores.get("nc", 0) + value["nc"]
            episodescores["nt"] = episodescores.get("nt", 0) + value["nt"]
            episodescores["np"] = episodescores.get("np", 0) + value["np"]

        #episodescores.update(self._compute_precision_recall_f1(episodescores["tp"], episodescores["fn"], episodescores["fp"]))
        episodescores.update(self._compute_precision_recall_f1(episodescores["nc"], episodescores["nt"], episodescores["np"]))

        return turnscores, episodescores
            