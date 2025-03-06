import re
from typing import Any, Dict, List, Optional

#from langchain import SQLDatabase, SQLDatabaseChain
from langchain_community.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain.agents import AgentExecutor, ConversationalAgent, Tool
from functools import partial
from langchain.agents.conversational.output_parser import ConvoOutputParser
from langchain.callbacks.manager import CallbackManagerForChainRun
from langchain.chains import LLMChain
#from langchain.llms import OpenAI
from langchain.llms.base import LLM
from langchain.pydantic_v1 import BaseModel, Field, ConfigDict
from langchain_community.llms import OpenAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
import tenacity
import json

import logging

from games.clemtod.dialogue_systems.xuetaldsys.booking import book_hotel, book_restaurant, book_taxi, book_train, book_slots
from games.clemtod.dialogue_systems.xuetaldsys.client import MyOpenAI
from games.clemtod.dialogue_systems.xuetaldsys.prompts import AGENT_TEMPLATE, DB_TEMPLATE_DICT
from games.clemtod.dialogue_systems.xuetaldsys.utils import (AGENT_COLOR, DB_PATH, HEADER_COLOR, HEADER_WIDTH,
                   OPENAI_API_KEY, RESET_COLOR, USER_COLOR, tenacity_retry_log)

INTERMEDIATE_STEPS_KEY = "intermediate_steps"
SQL_QUERY = "SQLQuery:"
SQL_RESULT = "SQLResult:"

logger = logging.getLogger(__name__)

dsys_logs = []



class SQLDatabaseChainWithCleanSQL(SQLDatabaseChain):

    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, Any]:
        logger.info(f"Inside SQLDatabaseChainWithCleanSQL:inputs: {inputs}")        
        _run_manager = run_manager or CallbackManagerForChainRun.get_noop_manager()
        input_text = f"{inputs[self.input_key]}\nSQLQuery:"
        _run_manager.on_text(input_text, verbose=self.verbose)
        # If not present, then defaults to None which is all tables.
        table_names_to_use = inputs.get("table_names_to_use")
        logger.info(f"table_names_to_use:{table_names_to_use}")
        table_info = self.database.get_table_info(table_names=table_names_to_use)
        llm_inputs = {
            "input": input_text,
            "top_k": self.top_k,
            "dialect": self.database.dialect,
            "table_info": table_info,
            "stop": ["\nSQLResult:"],
        }
        logger.info(f"llm_inputs:{llm_inputs}")
        intermediate_steps = []

        #dsys_role = 'assistant' if dsys_logs[-1]['role'] == 'user' else 'user'
        #dsys_logs.append({'role': dsys_role, 'content': llm_inputs})          
        sql_cmd = self.llm_chain.predict(
            callbacks=_run_manager.get_child(), **llm_inputs
        )

        dsys_role = 'assistant' if dsys_logs[-1]['role'] == 'user' else 'user'
        dsys_logs.append({'role': dsys_role, 'content': f"LLMChain Prediction:\n{sql_cmd}"})          

        logger.info(f"sql_cmd from llm_chain response:\n{sql_cmd}\n")
        sql_cmd = self.clean_sql(sql_cmd)  # NOTE: This is the new line
        intermediate_steps.append(sql_cmd)
        _run_manager.on_text(sql_cmd, color="green", verbose=self.verbose)
        logger.info(f"sql_cmd:\n{sql_cmd}\n")
        #input("Press Enter to continue...")
        result = self.database.run(sql_cmd)
        dsys_role = 'assistant' if dsys_logs[-1]['role'] == 'user' else 'user'
        dsys_logs.append({'role': dsys_role, 'content': f"DBQuery Result: {result}"})        
        logger.info(f"DBresult-> {result}, self.return_direct = {self.return_direct}")
        #input("Press Enter to continue...")
        intermediate_steps.append(result)
        _run_manager.on_text("\nSQLResult: ", verbose=self.verbose)
        _run_manager.on_text(result, color="yellow", verbose=self.verbose)
        # If return direct, we just set the final result equal to the sql query
        if self.return_direct:
            final_result = result
        else:
            _run_manager.on_text("\nAnswer:", verbose=self.verbose)
            input_text += f"{sql_cmd}\nSQLResult: {result}\nAnswer:"
            llm_inputs["input"] = input_text
            final_result = self.llm_chain.predict(
                callbacks=_run_manager.get_child(), **llm_inputs
            )
            logger.info(f"final_result:{final_result}")
            _run_manager.on_text(final_result, color="green", verbose=self.verbose)
        chain_result: Dict[str, Any] = {self.output_key: final_result}
        if self.return_intermediate_steps:
            chain_result["intermediate_steps"] = intermediate_steps
        return chain_result
    
    def clean_sql(self, sql_cmd):
        logger.info(f"sql_cmd before cleaning:{sql_cmd}")

        if SQL_QUERY in sql_cmd:
            sql_cmd = sql_cmd.split(SQL_QUERY)[1].strip()
        if SQL_RESULT in sql_cmd:
            sql_cmd = sql_cmd.split(SQL_RESULT)[0].strip()

        sql_cmd = sql_cmd.strip()
        sql_cmd = sql_cmd.replace("```sql", "")
        sql_cmd = sql_cmd.replace("```sql_cmd", "")
        sql_cmd = sql_cmd.replace("```", "")
        sql_cmd = sql_cmd.replace("SQLQuery:", "").strip()
        sql_cmd = sql_cmd.strip()
        logger.info(f"sql_cmd after cleaning:{sql_cmd} {type(sql_cmd)}")

        sql_cmd = re.sub(r"name (=|LIKE) '(.*'.*)'", r'name \1 "\2"', sql_cmd)
        logger.info(f"Change1: {sql_cmd}, {type(sql_cmd)}")

        sql_cmd = re.sub(r'\\"([a-zA-Z_]+)\\"', r'\1', sql_cmd)
        logger.info(f"Change2: {sql_cmd}, {type(sql_cmd)}")

        if sql_cmd[0] == '"' and sql_cmd[-1] == '"':
            sql_cmd = sql_cmd[1:-1]
        if sql_cmd[0] == "'" and sql_cmd[-1] == "'":
            sql_cmd = sql_cmd[1:-1]

        logger.info(f"returning sql_cmd as:{sql_cmd}")
        return sql_cmd



class LangChainLLMWrapper(LLM):
    player_llm: Any = Field(..., exclude=True)  # Exclude from Pydantic validation

    model_config = ConfigDict(extra="allow") 

    def __init__(self, player_llm, **kwargs):
        super().__init__(**kwargs)
        self.player_llm = player_llm  # Store your custom LLM instance

    @property
    def _llm_type(self) -> str:
        return "custom-llm-wrapper"

    def _call(self, messages: str, stop: Optional[List[str]] = None, **kwargs) -> str:
        """
        Calls the custom LLM framework and returns the output.
        """
        current_turn = kwargs.get('current_turn', -1)
        logger.info(f"LangChainLLMWrapper _call messages={messages} current_turn={current_turn}")
        prompt = [{'role': 'user', 'content': messages}]
        prompt, raw_answer, answer = self.player_llm(prompt, current_turn, None)

        logger.info(f"LangChainLLMWrapper _call raw_answer={raw_answer} answer={answer}")

        dsys_role = 'assistant' if dsys_logs[-1]['role'] == 'user' else 'user'
        #dsys_logs.append({'role': dsys_role, 'content': f"Follow-up: {answer}"})
        dsys_logs.append({'role': dsys_role, 'content': {'prompt': prompt, 'raw_answer': raw_answer,
                                                                    'answer': f"Agent Follow-up: {answer}"}})
        return answer



class Agent:

    def __init__(self, model, player_llm, db_path):
        logger.info(f"Agent __init__ model={model}")
        self.model = model
        self.player_llm = player_llm
        self.db_path = db_path        
        self.agent_executor = None
        self.genslots = {}
        self.reset()

    def reset(self):
        self.agent_executor = self.prepare_agent_executor(self.model, self.player_llm, self.db_path)

    @staticmethod
    def prepare_db_tools(llm, db_path):
        #DB_URI = f'sqlite:///{db_path}'
        #logger.info(f"DB_URI:{DB_URI}")
        def prepare_db_one_tool(domain, name, domain_db_uri):
            logger.info(f"prepare_db_one_tool: domain = {domain}, name = {name}")
            db = SQLDatabase.from_uri(
                database_uri=domain_db_uri,
                include_tables=[domain],
                sample_rows_in_table_info=5,
            )
            db_prompt = PromptTemplate.from_template(DB_TEMPLATE_DICT[domain])
            logger.info(f"db_prompt:{db_prompt}")
            sql_chain = SQLDatabaseChainWithCleanSQL.from_llm(
                db=db, llm=llm, prompt=db_prompt, top_k=10, verbose=True)
            tool = Tool(func=sql_chain.run, name=name, description='')
            return tool
        
        # domain (table, prompt), name
        db_info = [
            ('restaurant', 'Restaurant Query'),
            ('hotel', 'Hotel Query'),
            ('attraction', 'Attraction Query'),
            ('train', 'Train Query'),
        ]
        tools = []
        for domain, name in db_info:
            if domain not in DB_TEMPLATE_DICT:  # TODO
                continue
            domain_db_uri = f'sqlite:///{db_path}/{domain}-dbase.db'
            logger.info(f"domain_db_uri:{domain_db_uri} db_path:{db_path}, domain:{domain}")
            tool = prepare_db_one_tool(domain, name, domain_db_uri)
            tools.append(tool)

        logger.info(f"tools = {tools}")
        return tools

    @staticmethod
    def prepare_book_tools(db_path):
        book_restaurant_partial = partial(book_restaurant, f"{db_path}/restaurant-dbase.db")
        book_hotel_partial = partial(book_hotel, f"{db_path}/hotel-dbase.db")
        book_train_partial = partial(book_train, f"{db_path}/train-dbase.db")
        book_taxi_partial = partial(book_taxi, db_path)
        tools = [
            Tool(func=book_restaurant_partial, name='Restaurant Reservation', description=''),
            Tool(func=book_hotel_partial, name='Hotel Reservation', description=''),
            Tool(func=book_train_partial, name='Train Tickets Purchase', description=''),
            Tool(func=book_taxi_partial, name='Taxi Reservation', description=''),
        ]
        return tools

    @staticmethod
    def prepare_agent_executor(model, player_llm, db_path):
        # LLM
        #assert model.startswith('text-davinci-') or model.startswith('gpt-3.5-')
        '''
        if model.startswith('text-davinci-'):
            llm = OpenAI(
                model_name=model,
                temperature=0,
                max_tokens=-1,
                openai_api_key=OPENAI_API_KEY,
            )
        else:

        llm = MyOpenAI(
            model_name=model,
            player_llm=player_llm,
            temperature=0,
            # max_tokens=-1,
            openai_api_key=OPENAI_API_KEY,
        )
        '''
        llm = LangChainLLMWrapper(player_llm)
        # Tools
        tools = []
        tools += Agent.prepare_db_tools(llm, db_path)
        tools += Agent.prepare_book_tools(db_path)

        # Agent
        HUMAN_PREFIX = 'Human'
        AI_PREFIX = 'AI Assistant'

        prompt_temp = PromptTemplate.from_template(AGENT_TEMPLATE)
        logger.info(f"prompt_temp:{prompt_temp}")

        llm_chain = LLMChain(
            llm=llm,
            prompt=prompt_temp,
        )
        agent = ConversationalAgent(
            llm_chain=llm_chain,
            ai_prefix=AI_PREFIX,
            output_parser=ConvoOutputParser(ai_prefix=AI_PREFIX)
        )

        memory = ConversationBufferMemory(
            human_prefix=HUMAN_PREFIX,
            ai_prefix=AI_PREFIX,
            memory_key='chat_history',
        )
        agent_executor = AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=tools,
            memory=memory,
            max_iterations=5,
            verbose=True,
        )
        return agent_executor

    def __call__(self, user_utter, current_turn, callbacks=None):
        logger.info(f"Agent __call__ user_utter={user_utter} current_turn = {current_turn} callbacks ={callbacks}")

        global dsys_logs
        dsys_logs = [{'role': 'user', 'content': f"User Input: {user_utter}"}]
        #agent_utter = self.agent_executor.run(user_utter, current_turn, callbacks=callbacks)
        try:
            agent_response = self.agent_executor.invoke({
                                "input": user_utter,  # Required input for LangChain # Extra argument for custom LLM wrapper
                            }, current_turn=current_turn, callbacks=callbacks)
        except Exception as e:
            logger.error(f"Agent __call__ exception: {e}")
            agent_response = {'input': user_utter,
                'output': 'I am sorry, I am unable to process your request at the moment. Please try again later.', 'chat_history': []}
        
        agent_chat_history = agent_response['chat_history']
        agent_utter = agent_response['output']
        agent_utter = agent_utter.replace("```", "").strip()
        logger.info(f"Agent __call__ agent_utter={agent_utter}")
        dsys_logs.append({'role': 'assistant', 'content': f"AI Assistant: {agent_utter}"})

        return agent_utter, dsys_logs
    
    def run_old(self):
        self.reset()

        turn_idx = 1
        while True:
            print(HEADER_COLOR + '=' * HEADER_WIDTH + f' Turn {turn_idx} ' + '=' * HEADER_WIDTH + RESET_COLOR, end='\n\n')

            # User
            print(USER_COLOR + f'User: ', end='')
            user_input = input('User: ').strip()
            if user_input in ['exit', 'e']:
                break
            print(USER_COLOR + f'{user_input}' + RESET_COLOR, end='\n')

            # Agent
            agent_utter = self(user_input)
            print()
            print(AGENT_COLOR + f'Inside Agent() AI Assistant: {agent_utter}' + AGENT_COLOR, end='\n\n')

            turn_idx += 1


    def run(self, user_input, current_turn):
        agent_utter, dsys_logs = self(user_input, current_turn)
        return agent_utter, dsys_logs

    def get_booking_data(self):
        logger.info(f"Returing generated data: {book_slots}")
        return book_slots


if __name__ == '__main__':
    agent = Agent(model='gpt-3.5-turbo-0301')
    agent.run()
