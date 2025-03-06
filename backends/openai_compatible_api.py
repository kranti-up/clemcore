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
            http_client=httpx.Client(verify=False),
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
    def generate_response(
        self, messages: List[Dict], respformat=None, json_schema=None
    ) -> Tuple[str, Any, str]:
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
        if respformat is None and json_schema is None:
            api_response = self.client.chat.completions.create(
                model=self.model_spec.model_id,
                messages=prompt,
                temperature=self.get_temperature(),
                max_tokens=self.get_max_tokens(),
            )
            # logger.info(f"1. api_response-> {api_response}")

            if api_response is None:
                logger.info("Received None from OpenAI API, retrying...")
                raise ValueError("API response was None")

            message = api_response.choices[0].message
            if message.role != "assistant":  # safety check
                raise AttributeError(
                    "Response message role is "
                    + message.role
                    + " but should be 'assistant'"
                )
            response_text = message.content.strip()
            response = json.loads(api_response.json())

        else:
            if json_schema:
                # if self.model_spec.model_id == "llama-3.3-70b-versatile":
                api_response = self.client.chat.completions.create(
                    model=self.model_spec.model_id,
                    messages=prompt,
                    temperature=self.get_temperature(),
                    max_tokens=self.get_max_tokens(),
                    tools=[json_schema],
                    tool_choice="auto",
                )

                if (
                    api_response is None
                    or api_response.choices is None
                    or len(api_response.choices) == 0
                    or api_response.choices[0].message is None
                    #or (api_response.choices[0].message.tool_calls is None and not api_response.choices[0].message.content)
                ):
                    raise ValueError(f"Invalid API response {api_response}")

                message = api_response.choices[0].message
                if message.role != "assistant":  # safety check
                    raise AttributeError(
                        "Response message role is "
                        + message.role
                        + f" but should be 'assistant' api_response: {api_response}"
                    )

                try:
                    tool_calls = (
                        api_response.choices[0].message.tool_calls
                        if hasattr(api_response.choices[0].message, "tool_calls")
                        else []
                    )
                    if tool_calls:
                        function_call = (
                            tool_calls[0].function
                            if hasattr(tool_calls[0], "function")
                            else None
                        )

                        if function_call:
                            arguments = (
                                function_call.arguments
                                if hasattr(function_call, "arguments")
                                else None
                            )
                            if arguments:
                                response = json.loads(api_response.json())
                                response_text = arguments  # tool_output_dict
                    else:
                        logger.error(
                            f"No tool_calls inside response message: api_response = {api_response}"
                        )
                        response_text = message.content.strip()
                        response = json.loads(api_response.json())

                    """
                    if not tool_calls:
                        raise ValueError(f"No tool_calls inside response message: api_response = {api_response}")

                    
                    function_call = tool_calls[0].function if hasattr(tool_calls[0], 'function') else None
        
                    
                    if not function_call:
                        raise ValueError(f"No function inside tool_calls api_response = {api_response}")
                    
                    arguments = function_call.arguments if hasattr(function_call, 'arguments') else None
                
                    
                    if not arguments:
                        raise ValueError(f"No arguments inside function call api_response = {api_response}")
                    
                    #tool_output_dict = json.loads(arguments)  # Convert JSON string to Python dictionary
                    response = json.loads(api_response.json()) 
                    response_text = arguments#tool_output_dict
                    """

                except (IndexError, KeyError, json.JSONDecodeError) as e:
                    raise ValueError(
                        f"Error while extracting tool output: {e} api_response = {api_response}"
                    )
            else:
                use_format = []
                for rformat in respformat:
                    uformat = {"type": "function", "function": rformat}
                    use_format.append(uformat)

                # if self.model_spec.model_id == "llama-3.3-70b-versatile":
                api_response = self.client.chat.completions.create(
                    model=self.model_spec.model_id,
                    messages=prompt,
                    temperature=self.get_temperature(),
                    max_tokens=self.get_max_tokens(),
                    # response_format={'type': 'json_object'}
                    tools=use_format,
                )

                # logger.info(f"2. api_response-> {api_response}")
                if api_response is None:
                    logger.info("Received None from OpenAI API, retrying...")
                    raise ValueError("API response was None")

                message = api_response.choices[0].message
                if message.role != "assistant":  # safety check
                    raise AttributeError(
                        "Response message role is "
                        + message.role
                        + " but should be 'assistant'"
                    )
                response_text = message.content.strip()
                response = json.loads(api_response.json())

                if tool_calls := message.tool_calls:
                    response_text = tool_calls[0]
                else:
                    response_text = message.content.strip()

                    match = re.match(
                        r"<function=(\w+)(\{.*\})</function>", response_text
                    )
                    if match:
                        function_name = match.group(1)  # Extract function name
                        function_args_json = match.group(2)  # Extract JSON string
                        try:
                            function_args = json.loads(
                                function_args_json
                            )  # Convert to Python dictionary
                        except json.JSONDecodeError:
                            function_args = None  # Handle JSON parsing errors

                        response_text = {
                            "name": function_name,
                            "parameters": function_args,
                        }

                    else:
                        try:
                            response_text = json.loads(response_text)
                        except Exception as e:
                            response_text = response_text

        return prompt, response, response_text
