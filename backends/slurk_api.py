import multiprocessing
from multiprocessing import Manager, Event
import threading
import time
from typing import List, Dict, Tuple, Any, AsyncGenerator
from retry import retry
import requests
import backends
from backends.utils import ensure_messages_format

from backends.slurk_process import SlurkProcess

logger = backends.get_logger(__name__)

NAME = "slurk"

class SlurkAI(backends.Backend):

    def __init__(self, config=None):
        print(f"SlurkAI __init__, config = {config}")
        self.config = config or {}

    def list_models(self):
        return ["slurk"]
        # [print(n) for n in names]   # 2024-01-10: what was this? a side effect-only method?

    def get_model_for(self, model_spec: backends.ModelSpec) -> backends.Model:
        return SlurkInput(self.config, model_spec)
    
class SlurkInput(backends.Model):
    def __init__(self, config, model_spec):
        super().__init__(model_spec)
        print(f"SlurkInput __init__ config: {config}, model_spec: {model_spec}")
        self.manager = Manager()
        self.input_event = Event()
        self.response_queue = multiprocessing.Queue()
        self.pending_user_input = self.manager.Value(str, None)
        self.slurkprocess = SlurkProcess(1, "dmsystem", self.response_queue, self.input_event, self.cb_from_ui)
        self.launch_ui()
        print("SlurkInput __init__ done")

    @retry(tries=3, delay=0, logger=logger)
    @ensure_messages_format
    def generate_response(self, messages: List[Dict]) -> Tuple[str, Any, str]:
        """Get response for either user input or DM response."""
        print("Entering generate_response")

        prompt = messages
        input_message = messages[-1]["content"]

        if "SaveGoal" in input_message:
            extmsg = input_message.split("SaveGoal:")
            print(extmsg)
            welcomemsg = extmsg[0].strip()
            goal = extmsg[1].strip()
            self.setgoal(goal)
            input_message = welcomemsg

        print(f"Sending DM message to the UI: {input_message}")
        # Send the user input to the UI
        #self.response_queue.put(input_message) 
        self.slurkprocess.send_gm_response(input_message)

        print(f"Waiting for user input")
        #while not self.input_event.is_set():
        #    time.sleep(0.1)  # Poll until user input is available
        #self.input_event.clear()

        while True:
            uinput = self.slurkprocess.retrievelogs()
            if uinput:
                break
            time.sleep(0.1)

        print(f"User input received {uinput}")
        user_input = uinput#self.pending_user_input.value
        slurk_response = {"model": "gradio", "choices": [{"message": {"role": "assistant", "content": user_input}}]}
        print(f"Exiting generate_response: {user_input}")
        return prompt, slurk_response, user_input   
    
    def cb_from_ui(self, user_input):
        print(f"cb_from_ui: {user_input}")
        self.pending_user_input.value = user_input
        self.input_event.set()

    def is_server_ready(self, url):
        """Checks if the server is responding"""
        try:
            response = requests.get(url, timeout=2)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            return True
        except requests.exceptions.RequestException:
            return False


    def launch_ui(self):
        """Launch the UI."""
        print("Launching UI")
        self.slurkprocess.run()
        print("Slurk app launched in a separate process.") 
        time.sleep(5)

    def setgoal(self, goal):
        print(f"SlurkInput setgoal: {goal}")
        self.slurkprocess.setgoal(goal)

    