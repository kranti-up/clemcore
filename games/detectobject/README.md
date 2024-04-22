1. Install the clemgame requirements (preferably in a virtual environment)
2. Setup the path
     * Run the following command inside the clemgame directory
        * <..../clemgame> source prepare_path.sh
3. Steps to run a game (run from the directory: <..../clemgame>)
     * Generate game instances
        * python games/detectobject/instancegeneratory.py
        * Current test instances are available in detectobject/in/
     * Tweaks to the prompt
        * Current prompt is available in detectobject/resources/initial_prompts/
     * Run the game
        * python scripts/cli.py run -m <model_name> -g detectobject
        * clembench/backends/model_registry.json contains the model names
            * To use HuggingFace Remote API Models, use the models
                * remote-codeLlama-34b-instruct-hf, remote-mistral-7b-instruct-v0.2, remote-llama-2-7b-chat-hf
                * Example
                    * python scripts/cli.py run -m remote-codeLlama-34b-instruct-hf -g detectobject
            * Can add new models by adding them to the model_registry.json file
     * Score the game
        * python scripts/cli.py score -g detectobject
        * For the overall scores
          * python games/detectobject/utils/overallscores.py
            * This stores the overall_scores.json in results/  
     * Transcribe the game
        * python scripts/cli.py transcribe -g detectobject
        * Transcripts for the current tests are available in results/<model_name>/episode_<num>/transcript.html