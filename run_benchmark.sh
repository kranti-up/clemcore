#!/bin/bash
# Usage: ./run_benchmark.sh

source prepare_path.sh

version="v2.0"
results="results/${version}"
games=(
  #"imagegame"
  #"referencegame"
  "taboo"
  #"wordle"
  #"wordle_withclue"
  #"wordle_withcritic"
  #"privateshared"
  )
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

for game in "${games[@]}"; do
  for model in "${models[@]}"; do
    echo "Running ${model} on ${game}"
    # currently, instances.json is the default file for the current benchmark version
    # older files are being renamed retrospectively, but the framework also allows
    # to input a specific instances file, so we could also use the version number here like this: -i instances_"${version}".json
    { time python3 scripts/cli.py run -g "${game}" -m "${model}" -i instances.json -r "${results}"; } 2>&1 | tee runtime."${game}"."${model}".log
    # note that cli.py currently doesn't always throw errors, so always check clembench.log (in clembench)
  done
done

# if errors occur during the run, we don't want to go on with the evaluation automatically,
# so maybe move this to a separate script

#for game in "${games[@]}"; do
  #echo "Transcribing ${game}"
  #{ time python3 scripts/cli.py transcribe -g "${game}" -r "${results}"; } 2>&1 | tee runtime.transcribe."${game}".log
  #echo "Scoring ${game}"
  #{ time python3 scripts/cli.py score -g "${game}" -r "${results}"; } 2>&1 | tee runtime.score."${game}".log
  #echo "Evaluating ${game}"
  #{ time python3 evaluation/bencheval.py -p "${results}"; }
#done

echo "==================================================="
echo "FINISHED: Benchmark Run Version ${version}"
echo "==================================================="