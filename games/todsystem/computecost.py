import os
import json

API_PRICE = {
    'gpt-4o': {
        'input': 0.0025 / 1000,
        'cached': 0.00125 / 1000,
        'output': 0.01 / 1000,
    },
    'gpt-4o-2024-11-20': {
        'input': 0.0025 / 1000,
        'cached': 0.00125 / 1000,
        'output': 0.01 / 1000,
    },
    'gpt-4o-2024-08-06': {
        'input': 0.0025 / 1000,
        'cached': 0.00125 / 1000,
        'output': 0.01 / 1000,
    },
    'gpt-4o-mini': {
        'input': 0.00015 / 1000,
        'cached': 0.000075 / 1000,
        'output': 0.0006 / 1000,
    },    
    'gpt-4o-mini-2024-07-18': {
        'input': 0.00015 / 1000,
        'cached': 0.000075 / 1000,
        'output': 0.0006 / 1000,
    },      
    'deepseek-chat': {
        'input': 0.0025 / 1000,
        'cached': 0.00125 / 1000,
        'output': 0.0011 / 1000,
    },
    'meta-llama/llama-3.3-70b-instruct': {
        'input': 0.00012 / 1000,
        'cached': 0.0,
        'output': 0.0003 / 1000,
    },
    'meta-llama/llama-3.1-8b-instruct': {
        'input': 0.00002 / 1000,
        'cached': 0.0,
        'output': 0.00005 / 1000,
    },    
}

def calc_openai_cost(model, usage):
    if model in API_PRICE:
        price = API_PRICE[model]

        prompt_tokens = usage['prompt_tokens']
        if "prompt_tokens_details" in usage and usage["prompt_tokens_details"]:
            cached_tokens = usage["prompt_tokens_details"]["cached_tokens"]
            if cached_tokens:
                prompt_tokens -= cached_tokens
        else:
            cached_tokens = 0

        cost = prompt_tokens * price['input'] + cached_tokens * price['cached'] + usage['completion_tokens'] * price['output']
    else:
        raise ValueError(f'{model = }')
    return cost, {"prompt_tokens": prompt_tokens, "cached_tokens": cached_tokens, "completion_tokens": usage['completion_tokens']}


def compute_cost(base_dir):
    results = {}    

    for model in os.listdir(base_dir):
        if model.endswith(".json"):
            continue
        model_path = os.path.join(base_dir, model)
        for game in os.listdir(model_path):
            if game not in results:
                results[game] = {}
            if model not in results[game]:
                results[game][model] = {}
            game_path = os.path.join(model_path, game)
            for exp in os.listdir(game_path):
                exp_path = os.path.join(game_path, exp)
                if not os.path.isdir(exp_path):
                    continue

                if exp not in results[game][model]:
                    results[game][model][exp] = 0.0

                episode_costs = []
                episode_tokens = {}
                for episode in os.listdir(exp_path):
                    if episode.endswith(".json"):
                        continue

                    episode_path = os.path.join(exp_path, episode)
                    for filename in os.listdir(episode_path):
                        if not filename in ["requests.json"]:
                            continue

                        with open(os.path.join(episode_path, filename), "r") as f:
                            requests_data = json.load(f)

                        cost = 0.0
                        numtokens = []
                        for request in requests_data:
                            if "raw_response_obj" not in request:
                                print(f"Skipping {request} in {episode_path}")
                                continue
                            cost_val, details = calc_openai_cost(request["raw_response_obj"]['model'],
                                                     request["raw_response_obj"]['usage'])
                            cost += cost_val
                            numtokens.append(details)
                            
                        episode_costs.append(cost)
                        for nt in numtokens:
                            for key, value in nt.items():
                                if key not in episode_tokens:
                                    episode_tokens[key] = 0
                                episode_tokens[key] += value
                results[game][model][exp] = {"total": round(sum(episode_costs), 2), "episodes": episode_costs,
                                              "tokens": episode_tokens}
                results[game][model][exp]["cost"] = round(sum(episode_costs), 2)




    for game in results:
        overall_cost = 0.0
        overall_tokens_count = 0
        for model in results[game]:
            overall_cost += sum([exp["total"] for exp in results[game][model].values()])
            print(f"{game}--{model}-> Cost: {round(overall_cost, 2)}")
            results[game][model]["overall"] = round(overall_cost, 2)
            overall_tokens = {}
            for exp in results[game][model]:
                if exp == "overall":
                    continue
                for key, value in results[game][model][exp]["tokens"].items():
                    if key not in overall_tokens:
                        overall_tokens[key] = 0
                    overall_tokens[key] += value
                results[game][model][exp]["total_tokens"] = overall_tokens.get("prompt_tokens", 0) + overall_tokens.get("cached_tokens", 0) + overall_tokens.get("completion_tokens", 0)

            prompt_tokens = 0
            cached_tokens = 0
            completion_tokens = 0
            for exp in results[game][model]:
                if exp in ["overall", "overall_tokens"]:
                    continue
                prompt_tokens += results[game][model][exp]["tokens"].get("prompt_tokens", 0)
                cached_tokens += results[game][model][exp]["tokens"].get("cached_tokens", 0)
                completion_tokens += results[game][model][exp]["tokens"].get("completion_tokens", 0)
            overall_tokens_count = prompt_tokens + cached_tokens + completion_tokens
            prompt_tokens = round(prompt_tokens/1000000, 3)
            cached_tokens = round(cached_tokens/1000000, 3)
            completion_tokens = round(completion_tokens/1000000, 3)
            results[game][model]["overall_tokens"] = {"prompt_tokens": f"{prompt_tokens}M",
                                                        "cached_tokens": f"{cached_tokens}M",
                                                        "completion_tokens": f"{completion_tokens}M",
                                                        "total_tokens": f"{round(overall_tokens_count/1000000, 3)}M"}
                                                     
            print(f"{game}--{model}-> Tokens: {round(overall_tokens_count/1000000, 3)}M")



    with open(os.path.join(base_dir, "costs.json"), "w") as f:
        json.dump(results, f, indent=2)



if __name__ == '__main__':
    compute_cost("/home/admin/Desktop/codebase/cocobots/clembenchfork_dm_code/clembench/test_res_single/")




