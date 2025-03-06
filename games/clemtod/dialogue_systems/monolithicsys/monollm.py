import json

from clemgame import get_logger
from games.clemtod.dialogue_systems.monolithicsys.utils import cleanupanswer
from games.clemtod.processfunccallresp import ProcessFuncCallResp

logger = get_logger(__name__)

class MonoLLM:
    def __init__(self, model_id, prompts_dict, player_dict, resp_json_schema):
        self.model_id = model_id
        self.prompts_dict = prompts_dict
        self.player_b = player_dict["monollm_player"]
        self.resp_json_schema = resp_json_schema
        self.extracted_slots = None
        self.booking_slots = None

        self.player_b.history.append({"role": "user", "content": prompts_dict["prompt_b"]})
        self.processresp = ProcessFuncCallResp()

    def run(self, utterance, current_turn):
        self._append_utterance("user", utterance)

        prompt, raw_answer, answer = self.player_b(self.player_b.history,
                                                   current_turn, None, self.resp_json_schema)
        self._append_utterance("assistant", answer)
        
        #answer_clean = cleanupanswer(answer)

        answer_cleanup = cleanupanswer(answer)
        logger.info(f"Answer from the model: {answer}, {type(answer)}, answer_cleanup = {answer_cleanup}")        
        llm_response, error = self.processresp.run(answer_cleanup)

        promptlogs = [({"role": "assistant", "content": f"model response before processing: {answer}"})]

        if error:
            promptlogs.append({"role": "assistant", "content": f"error while parsing the data: {error}"})


        promptlogs.append({'role': "monollm", 'content': {'prompt': prompt, 'raw_answer': raw_answer,
                                                                    'answer': llm_response}})

        return promptlogs, raw_answer, llm_response

    def _process_response(self, answer):
        try:
            response = json.loads(answer)
            if "status" in response and "details" in response:
                if response["status"] == "db-query":
                    self.extracted_slots = response["details"]
                elif response["status"] == "validate-booking":
                    self.booking_slots = response["details"]
        
        except Exception as error:
            logger.error(f"Error in _parse_response: {error}")


    def _append_utterance(self, role, utterance):
        if role == "assistant":
            self.player_b.history.append({"role": role, "content": utterance})
        else:
            if len(self.player_b.history) == 1:
                #TODO: check for cases, where player_b.history is empty
                self.player_b.history[-1]["content"] += "\n\n" + utterance
                self.player_b.history[-1]["content"] = self.player_b.history[-1]["content"].strip()
            else:
                if "DATABASE RETRIEVAL RESULTS:" in utterance:
                    turn_prompt = self.prompts_dict["dbquery_prompt_b"]
                elif "BOOKING VALIDATION STATUS:" in utterance:
                    turn_prompt = self.prompts_dict["validbooking_prompt_b"]
                else:
                    turn_prompt = self.prompts_dict["turn_prompt_b"]

                self.player_b.history.append({"role": role, "content": turn_prompt + "\n\n" + utterance})

    def get_booking_data(self):
        #Since this is Monolithic LLM System, the data is not stored in the system, instead it is on the LLM side to return this info in booking call
        return {}
    
    def get_entity_slots(self):
        #Since this is Monolithic LLM System, the data is not stored in the system, instead it is on the LLM side to return this info in booking call
        return {}