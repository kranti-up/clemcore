from typing import List, Dict, Tuple, Any
from retry import retry

import json
import openai
import backends
import httpx
import re

from backends.utils import ensure_messages_format

logger = backends.get_logger(__name__)

NAME = "generic_openai_compatible"


class GenericOpenAI(backends.Backend):

    def __init__(self):
        creds = backends.load_credentials(NAME)
        self.client = openai.OpenAI(
            base_url=creds[NAME]["base_url"],
            api_key=creds[NAME]["api_key"],
            ### TO BE REVISED!!! (Famous last words...)
            ### The line below is needed because of
            ### issues with the certificates on our GPU server.
            http_client=httpx.Client(verify=False)
        )

    def list_models(self):
        models = self.client.models.list()
        names = [item.id for item in models.data]
        names = sorted(names)
        return names

    def get_model_for(self, model_spec: backends.ModelSpec) -> backends.Model:
        return GenericOpenAIModel(self.client, model_spec)


class GenericOpenAIModel(backends.Model):

    def __init__(self, client: openai.OpenAI, model_spec: backends.ModelSpec):
        super().__init__(model_spec)
        self.client = client

    @retry(tries=3, delay=1, logger=logger)
    @ensure_messages_format
    def generate_response(self, messages: List[Dict], respformat=None) -> Tuple[str, Any, str]:
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
        prompt = messages
        if respformat is None:
            api_response = self.client.chat.completions.create(model=self.model_spec.model_id, messages=prompt,
                                                            temperature=self.get_temperature(),
                                                            max_tokens=self.get_max_tokens())
            #logger.info(f"1. api_response-> {api_response}")

            if api_response is None:
                logger.info("Received None from OpenAI API, retrying...")
                raise ValueError("API response was None")

            message = api_response.choices[0].message
            if message.role != "assistant":  # safety check
                raise AttributeError("Response message role is " + message.role + " but should be 'assistant'")
            response_text = message.content.strip()
            response = json.loads(api_response.json())

        else:
            '''
            use_format = {}
            for key, value in respformat.items():
                if key == "schema":
                    use_format[key] = {}
                    use_format[key]["type"] = "json_object"
                    use_format[key]["properties"] = value["properties"]
                    use_format[key]["required"] = value["required"]
                else:
                    use_format[key] = value

            use_format = {}
            for key, value in respformat.items():
                if key == "schema":
                    use_format = value
            '''
            use_format = []
            for rformat in respformat:
                uformat = {"type": "function", "function": rformat}
                use_format.append(uformat)

            #if self.model_spec.model_id == "llama-3.3-70b-versatile":
            api_response = self.client.chat.completions.create(model=self.model_spec.model_id, messages=prompt,
                                                            temperature=self.get_temperature(),
                                                            max_tokens=self.get_max_tokens(),
                                                            #response_format={'type': 'json_object'}
                                                            tools=use_format,
                                                            )
 
            #logger.info(f"2. api_response-> {api_response}")
            if api_response is None:
                logger.info("Received None from OpenAI API, retrying...")
                raise ValueError("API response was None")


            message = api_response.choices[0].message
            if message.role != "assistant":  # safety check
                raise AttributeError("Response message role is " + message.role + " but should be 'assistant'")
            response_text = message.content.strip()
            response = json.loads(api_response.json())
 
            '''
            try:
                response_text = json.loads(response_text)
                if "details" in response_text:
                    if isinstance(response_text["details"], str):
                        try:
                            response_text["details"] = json.loads(response_text["details"])
                        except:
                            response_text["details"] = response_text["details"]

                response_text = json.dumps(response_text)

            except Exception as e:
                response_text = response_text
            '''
            if tool_calls := message.tool_calls:
                response_text = tool_calls[0]
            else:
                #print(f"No tool calls found. {message}")
                response_text = message.content.strip()

                match = re.match(r"<function=(\w+) ({.*})</function>", response_text)

                if match:
                    function_name = match.group(1)  # Extract function name
                    function_args_json = match.group(2)  # Extract JSON string
                    try:
                        function_args = json.loads(function_args_json)  # Convert to Python dictionary
                    except json.JSONDecodeError:
                        function_args = None  # Handle JSON parsing errors

                    response_text = {"name": function_name, "parameters": function_args}

                else:
                    try:
                        response_text = json.loads(response_text)
                    except Exception as e:
                        response_text = response_text


        return prompt, response, response_text
