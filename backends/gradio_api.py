import multiprocessing
from multiprocessing import Manager, Event
import threading
import time
from typing import List, Dict, Tuple, Any, AsyncGenerator
from retry import retry
import requests
import backends
from backends.utils import ensure_messages_format
import queue

import gradio as gr


logger = backends.get_logger(__name__)

NAME = "gradio"

class GradioAI(backends.Backend):

    def __init__(self, config=None):
        self.config = config or {}

    def list_models(self):
        return ["gradio"]
        # [print(n) for n in names]   # 2024-01-10: what was this? a side effect-only method?

    def get_model_for(self, model_spec: backends.ModelSpec) -> backends.Model:
        return GradioInput(self.config, model_spec)
    
class GradioInput(backends.Model):
    def __init__(self, config, model_spec):
        super().__init__(model_spec)
        self.manager = Manager()
        self.chat_history = self.manager.list()
        self.pending_user_input = self.manager.Value(str, None)
        self.input_event = Event()
        self.user_goal = None
        self.start_ui()

    @retry(tries=3, delay=0, logger=logger)
    @ensure_messages_format
    def generate_response(self, messages: List[Dict]) -> Tuple[str, Any, str]:
        print(f"Entering generate_response ")
        prompt = messages
        input_message = messages[-1]["content"]

        if "SaveGoal" in input_message:
            extmsg = input_message.split("SaveGoal:")
            print(extmsg)
            welcomemsg = extmsg[0].strip()
            goal = extmsg[1].strip()
            self.set_user_goal(goal)
            input_message = welcomemsg

        self.chat_history.append({"role": "assistant", "content": input_message})
        #print('Set the data to Bot Queue')
        #dmresp = {"role": "assistant", "content": f"dm_response {self.counter}"}

        #self.ui_queue.put({"chat_history": dmresp})
        time.sleep(0.1)
        print(f"Waiting for user input")
        # Wait for user input
        while not self.input_event.is_set():
            time.sleep(0.1)  # Poll until user input is available
        self.input_event.clear() 
        user_input = self.pending_user_input.value
        print(f"user_input: {user_input}")
        self.pending_user_input.value = None
        #self.chat_history.append(("User", user_input))

        gradio_response = {"model": "gradio", "choices": [{"message": {"role": "assistant", "content": user_input}}]}
        print(f"Exiting generate_response: {user_input}")
        return prompt, gradio_response, user_input   


    def set_user_goal(self, user_goal):
        print(f"Entering set_user_goal: {user_goal}")
        self.user_goal = user_goal

    def get_user_goal(self):
        return self.user_goal
    
    def render_chat_interface(self):
        """Render the chat interface."""
        return "\n".join([f"{role}: {message}" for role, message in self.chat_history])  

    def get_current_history(self):
        return self.chat_history

    def launch_ui(self):
        def handleuserinput(user_input, chatbot):
            print(f"Entering handleuserinput: {user_input} {chatbot}")
            self.pending_user_input.value = user_input
            self.input_event.set() 
            self.chat_history.append({"role": "user", "content": user_input})
            #chat_history.append({"role": "assistant", "content": "Loading audio and video..."})    
            return "", self.chat_history

        def update_chatbot():
            print(f"Entering update_chatbot: chat_history = {self.chat_history}")
            return self.chat_history
        
        def update_usergoal():
            print(f"Entering update_usergoal: user_goal = {self.user_goal}")
            return self.user_goal
        

        with gr.Blocks() as interface:
            chatbot = gr.Chatbot(type="messages", value = self.get_current_history())#, every=0.5)
            usermsg = gr.Textbox(label="User message")
            #additionalinputs = gr.Textbox(label="User Goal", value = self.get_user_goal(), every=0.5, interactive=False)
            #button = gr.Button("Load audio and video")
            #button.click(load, None, chatbot)
            chatbot.change(update_chatbot, None, [chatbot])
            #additionalinputs.change(update_usergoal, None, [additionalinputs])
            usermsg.submit(handleuserinput, [usermsg, chatbot], [usermsg, chatbot])

        interface.launch()


    def start_ui(self):
        """Start the UI in a separate process."""
        self.ui_process = multiprocessing.Process(target=self.launch_ui)
        self.ui_process.start()        