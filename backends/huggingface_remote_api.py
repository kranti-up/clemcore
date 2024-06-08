from typing import List, Dict, Tuple, Any
from retry import retry
import requests

import json
import openai
import backends

logger = backends.get_logger(__name__)

NAME = "huggingface"
API_URL = "https://api-inference.huggingface.co/models/"


class HuggingfaceRemote(backends.Backend):

    def __init__(self):
        creds = backends.load_credentials(NAME)
        api_key = creds["huggingface"]["api_key"]
        self.client_headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def get_model_for(self, model_spec: backends.ModelSpec) -> backends.Model:
        return HuggingfaceRemoteModel(self.client_headers, model_spec)


class HuggingfaceRemoteModel(backends.Model):

    def __init__(self, client_headers: Dict, model_spec: backends.ModelSpec):
        super().__init__(model_spec)
        self.client_headers = client_headers
        self.llama__models = [
                "codellama/CodeLlama-34b-Instruct-hf",
                "mistralai/Mistral-7B-Instruct-v0.1",
            ]        

    @retry(tries=3, delay=0, logger=logger)
    def generate_response(self, messages: List[Dict]) -> Tuple[str, Any, str]:
        """
        :param messages: for example
                [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Who won the world series in 2020?"},
                    {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
                    {"role": "user", "content": "Where was it played?"}
                ]
        :return: the continuation
        """
        temperature = self.get_temperature() or 0.01

        if self.model_spec.model_id in self.llama__models:
            # chat completion
            prompt = ("".join([
                               f'[/INS] {m["content"]}.'
                               if m["role"] == "assistant"
                               else f'<s> [INS] {m["content"]}'
                               for m in messages
                            ]
                    )+ "[/INS]")
        else:
            prompt = "\n".join([m["content"] for m in messages])

        model_parameters = {
            "temperature": temperature,
            "max_new_tokens": self.get_max_tokens(),
            "num_return_sequences": 1,
        }
        payload = {"inputs": prompt, "parameters": model_parameters}
        model_url = f"{API_URL}"#f"{API_URL}{self.model_spec.model_id}"

        try:
            with requests.post(
                model_url, headers=self.client_headers, json=payload
            ) as api_response:
                response = api_response.json()
                if "error" in response:
                    response_text = response["error"]

                else:
                    response = response[0]
                    response_text = response["generated_text"]
                    if prompt in response_text:
                        response_text = response_text.replace(prompt, "").strip()

        except requests.RequestException as e:
            response_text = f"Request failed: {e}"


        return prompt, response, response_text
