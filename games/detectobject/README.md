1. Install the clemgame requirements (preferably in a virtual environment)
2. Setup the path
     * Run the following command inside the clemgame directory
        * <..../clemgame> source prepare_path.sh
3. Steps to run a game
     * Generate game instances
        * python games/detectobject/instancegeneratory.py
     * Run the game
        * python scripts/cli.py run -m <model_name> -g detectobject
     * Score the game
        * python scripts/cli.py score -g detectobject
     * Transcribe the game
        * python scripts/cli.py transcribe -g detectobject  