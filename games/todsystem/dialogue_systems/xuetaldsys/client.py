import json
import langchain
import langchain_community
import openai
from langchain.utils import get_from_dict_or_env
from pydantic import root_validator
import logging

logger = logging.getLogger(__name__)


#class ChatClientAdapter(openai.ChatCompletion):
class ChatClientAdapter(openai.OpenAI):

    @classmethod
    def create(cls, prompt, *args, **kwargs):
        # Pre-process
        assert len(prompt) == 1
        messages=[
            {'role': 'user', 'content': prompt[0]},
        ]
        # Core
        #completion = super().create(messages=messages, *args, **kwargs)
        completion = openai.OpenAI(api_key=openai.api_key).chat.completions.create(model=kwargs['model'],
                                                                                   messages=messages,
                                                                                   temperature=0,
                                                                                   max_tokens=kwargs['max_tokens'])

        response = completion.choices[0].message
        if response.role != "assistant":  # safety check
            raise AttributeError("Response message role is " + response.role + " but should be 'assistant'")
        response_text = response.content.strip()

        # Post-process
        for choice in completion.choices:
            assert choice.message.role == 'assistant'
            choice.text = choice.message.content
            choice.text = choice.text.strip()

        logger.info(f"Response text: {response_text}")

        return completion
    

class MyOpenAI(langchain_community.llms.OpenAI):

    def __new__(cls, *args, **kwargs):
        return super(langchain_community.llms.openai.BaseOpenAI, cls).__new__(cls)

    @root_validator(pre=True)
    def validate_environment(cls, values):
        logger.info(f"Validating environment: values = {values}")
        openai_api_key = get_from_dict_or_env(values, "openai_api_key", "OPENAI_API_KEY")
        openai.api_key = openai_api_key
        values["client"] = ChatClientAdapter
        return values
    

if __name__ == '__main__':
    OPENAI_API_KEY = ''

    openai.api_key = OPENAI_API_KEY

    llm = MyOpenAI(
        model_name='gpt-3.5-turbo',
        temperature=0,
        openai_api_key=OPENAI_API_KEY,
    )

    resp = llm("Tell me a joke")
    print(resp)
