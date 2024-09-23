#!/bin/bash
# Usage: ./run_benchmark.sh

source prepare_path.sh

games="game_selection.json"
version="v2.0"  # could potentially also be extracted from game_selection.json in clemgame/framework.py, see comments there
models=(
"mock"
#"claude-3-opus-20240229"
#"gpt-4-turbo-2024-04-09"
#"command-r-plus"
#"Llama-3-8b-chat-hf"
#"Llama-3-70b-chat-hf"
)

echo
echo "==================================================="
echo "RUNNING: Benchmark Run Version ${version}"
echo "==================================================="
echo


for model in "${models[@]}"; do
  echo "Running ${model}"
  # currently, instances.json is the default file for the current benchmark version
  # older files are being renamed retrospectively, but the framework also allows
  # to input a specific instances file, so we could also use the version number here like this: -i instances_"${version}".json
  { time python3 scripts/cli.py run -g "${games}" -m "${model}" -i instances.json -r "results/${version}"; } 2>&1 | tee runtime."${games}"."${model}".log
done

# if errors occur during the run, we don't want to go on with the evaluation automatically,
# so maybe move this to a separate script

#{ time python3 scripts/cli.py transcribe -g "${games}" -r "${results}"; } 2>&1 | tee runtime.transcribe."${games}".log
#{ time python3 scripts/cli.py score -g "${games}" -r "${results}"; } 2>&1 | tee runtime.score."${games}".log
#{ time python3 evaluation/bencheval.py -p "results/${version}"; }

echo "==================================================="
echo "FINISHED: Benchmark Run Version ${version}"
echo "==================================================="