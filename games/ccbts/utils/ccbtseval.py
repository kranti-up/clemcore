

from collections import Counter

from games.ccbts.utils.exactmatch import em_comparison
from games.ccbts.utils.codebleu_match import cb_comparison
from games.ccbts.utils.execscore import exec_comparison


class CCBTSEval:
    def __init__(self):
        pass

    def _compute_metrics(self, metrics, total):
        success = metrics["success"]
        failure = metrics["failure"]

        precision = round(success / total, 3) if total > 0 else 0
        recall = round(success / (success + failure), 3) if success + failure > 0 else 0
        f1_score = (
            round(2 * (precision * recall) / (precision + recall), 3)
            if precision + recall > 0
            else 0
        )
        return precision, recall, f1_score    

    def _cleanup_response(self, prediction):
        for key, value in prediction.items():
            if value:
                if "```python" in value:
                    value = value.replace("```python", "").strip()
                    prediction[key] = value
                if "```" in value:
                    value = value.replace("```", "").strip()
                    prediction[key] = value

        for key, value in prediction.items():
            if key == "function":
                if "Usage" in value:
                    if "Usage:" in value:
                        value = value.replace("Usage:", "").strip()
                        prediction[key] = value
                    elif "Usage" in value:
                        value = value.replace("Usage", "").strip()
                        prediction[key] = value

                    k1 = prediction[key].split("\n")
                    if k1[0] == ":":
                        k1 = k1[1:]
                    prediction[key] = "\n".join(k1)
                if "Function" in value:
                    prediction[key] = value.replace("Function", "")
            if key == "usage" and "Usage" in value:
                prediction[key] = value.replace("Usage", "").strip()

            if key == "output":
                if value[0] == ":":
                    value = value[1:].strip()
                    prediction[key] = value


    def _prepare_groundtruth(self, ground_truth):

        if "function" in ground_truth and "usage" in ground_truth:
            ground_truth["function"] = ground_truth["function"]+"\n"+ground_truth["usage"]


    def analyze(self, rows, cols, ground_truth, prediction):
        results = {
                    "exact_match": Counter(),
                    "codebleu": Counter(),
                    "exec_score": Counter(),
                  }

        #ground_truth = records["ground_truth"]
        #prediction = records["prediction"]
        #response = records["response"]

        #prediction = 
        self._prepare_groundtruth(ground_truth)
        self._cleanup_response(prediction)
        #print(prediction)

        em_match_type = em_comparison(ground_truth, prediction, results["exact_match"])
        #print(f"em_match_type: {em_match_type}")
        cb_match_type = cb_comparison(ground_truth, prediction, results["codebleu"])
        exec_match_type, exec_result = exec_comparison(rows, cols, ground_truth, prediction, results["exec_score"])
        print(exec_match_type, exec_result)

        #if not all(all(match_type == "success" for match_type in lst) for lst in [em_match_type, cb_match_type, exec_match_type]):
        return {
            "ground_truth": ground_truth,
            "prediction": prediction,
            #"response": response,
            "exact_match": em_match_type,
            "codebleu": cb_match_type,
            "exec_score": exec_match_type,
            "exec_result": exec_result,
        }

    def parse_results(self, rows, cols, records):

        if not all(key in records.get("action", {}) for key in ["groundtruth", "prediction"]):
            raise ValueError("Invalid results format: 'action', 'groundtruth', or 'prediction' missing")

        # Directly unpack the needed values
        groundtruth, prediction = records["action"]["groundtruth"], records["action"]["prediction"]

        n_turns = len(groundtruth)

        turn_scores = {turn: {'exact_match': 'failure', 'codebleu': 'failure', 'exec_score': 'failure'} for turn in range(1, n_turns+1)}
        episode_scores = {metric: {"precision": 0.0, "recall": 0.0, "f1_score": 0.0} for metric in ["exact_match", "codebleu", "exec_score"]}



        # Check if lengths match
        if len(groundtruth) != len(prediction) or list(groundtruth.keys()) != list(prediction.keys()):
            #raise ValueError(f"Mismatch in number of turns between groundtruth and prediction gt_len = {len(groundtruth)}, pred_len = {len(prediction)} gt_keys = {list(groundtruth.keys())}, pred_keys = {list(prediction.keys())}")
            return turn_scores, episode_scores
        # Raise an exception if any turn in groundtruth is missing in prediction
        missing_turns = set(groundtruth) - set(prediction)
        if missing_turns:
            #raise ValueError(f"Turns missing in prediction: {missing_turns}")
            return turn_scores, episode_scores           

        # Use dictionary comprehension for concise turn analysis
        turn_analysis = {
            turn: self.analyze(rows, cols, groundtruth[turn], prediction[turn])
            for turn in groundtruth
        }

        # Initialize analysis with counters
        episode_analysis = {metric: Counter() for metric in ["exact_match", "codebleu", "exec_score"]}
        episode_analysis["exec_result"] = {}

        for turn, analysis_results in turn_analysis.items():
            for metric, result in analysis_results.items():
                if metric in episode_analysis:
                    if metric == "exec_result":
                        episode_analysis[metric][turn] = result
                    else:
                        episode_analysis[metric][result] += 1

        #record_count = len(records)
        record_count = len(turn_analysis)
        for metric, counts in episode_analysis.items():
            if metric == "exec_result":
                continue
            precision, recall, f1_score = self._compute_metrics(counts, record_count)
            episode_analysis[metric].update({"precision": precision, "recall": recall, "f1_score": f1_score})

        return turn_analysis, episode_analysis


if __name__ == "__main__":
    records = {        "action": {
            "groundtruth": {
                "1": {
                    "function": "def wn(board, colors, x, y):\n    shapes = ['washer', 'nut']\n    for shape, color, dx, dy in zip(shapes, colors, [0, 0], [0, 0]):\n            put(board, shape, color, x + dx, y + dy)",
                    "output": "for row in range(8):\n    for col in range(0, 8, 2):\n        wn(board, colors=['red', 'yellow'],x=row, y=col)",
                    "total_code": "def wn(board, colors, x, y):\n    shapes = ['washer', 'nut']\n    for shape, color, dx, dy in zip(shapes, colors, [0, 0], [0, 0]):\n            put(board, shape, color, x + dx, y + dy)\nboard = init_board(8, 8)\nfor row in range(8):\n    for col in range(0, 8, 2):\n        wn(board, colors=['red', 'yellow'],x=row, y=col)"
                }
            },
            "prediction": {
                "1": {
                    "output": "wn(board, ['red', 'blue', 'green', 'yellow'], 0, 0)\nwn(board, ['red', 'blue', 'green', 'yellow'], 2, 0)\nwn(board, ['red', 'blue', 'green', 'yellow'], 4, 0)\nwn(board, ['red', 'blue', 'green', 'yellow'], 6, 0)\n\nInstruction\nPlace a 'bridge-h' object in the second row, spanning columns 2 and 3."
                }
            }
        }}
    '''
    records  = {"action": {
                    "groundtruth": {
                        "1": {
                            "output": "Function\ndef n2(board, shapes, colors, x, y):\n\tput(board, shapes[0], colors[0], x, y)\n\tput(board, shapes[1], colors[1], x, y+1)\n\nUsage\nn2(board, ['nut', 'nut'], ['red', 'blue'], 2,3)",
                            "function": "def n2(board, shapes, colors, x, y):\n\tput(board, shapes[0], colors[0], x, y)\n\tput(board, shapes[1], colors[1], x, y+1)",
                            "usage": "n2(board, ['nut', 'nut'], ['red', 'blue'], 2,3)"
                        }
                    },
                    "prediction": {
                        "1": {
                            "function": "```python\ndef n2(board, shapes, colors, x, y):\n    put(board, shapes[0], colors[0], x, y)\n    put(board, shapes[1], colors[1], x, y+1)\n```\n\nUsage\n```python\nn2(board, ['nut', 'nut'], ['red', 'blue'], 2, 3)\n```",
                            "usage": "```python\nn2(board, ['nut', 'nut'], ['red', 'blue'], 2, 3)\n```"
                        }
                    }
                }
            }
 
    records = {"action": {"groundtruth": {"1":{"output": "Function\ndef n_washer (board, colors, x, y):\n\n    put(board, \"washer\", colors[0], x, y)\n    put(board, \"nut\", colors[1], x, y)\n    \n\n    return board\n\nUsage\nboard = n_washer(board, ['red', 'yellow'], 7, 6)",
                "function": "def n_washer (board, colors, x, y):\n\n    put(board, \"washer\", colors[0], x, y)\n    put(board, \"nut\", colors[1], x, y)\n    \n\n    return board",
                "usage": "board = n_washer(board, ['red', 'yellow'], 7, 6)"}},
                           "prediction": {"1":{"function": ":\ndef n_washer(board, colors, x, y):\n    put(board, \"washer\", colors[0], x, y)\n    put(board, \"nut\", colors[1], x, y)\n    return board\n\nUsage:\nboard = n_washer(board, ['red', 'yellow'], 7, 7)",
                "usage": ":\nboard = n_washer(board, ['red', 'yellow'], 7, 7)"}}}} 
    '''
    ccbts_eval = CCBTSEval()
    turn_analysis, episode_analysis = ccbts_eval.parse_results(8, 8, records)
    print(episode_analysis)

