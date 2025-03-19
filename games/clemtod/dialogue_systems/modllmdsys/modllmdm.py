import time
import copy
from typing import Dict
import json

from clemgame import get_logger
from games.clemtod.utils import cleanupanswer
from games.clemtod.dialogue_systems.modllmdsys.players import ModLLMSpeaker
from games.clemtod.dialogue_systems.modprogdsys.intentdetector import IntentDetector
from games.clemtod.dialogue_systems.modprogdsys.slotextractor import SlotExtractor
from games.clemtod.dialogue_systems.modprogdsys.followupgenerator import FollowupGenerator
from games.clemtod.dialogue_systems.modprogdsys.dbqueryformatter import DBQueryFormatter
from games.clemtod.dialogue_systems.modprogdsys.bookingformatter import BookingFormatter
from games.clemtod.processfunccallresp import ProcessFuncCallResp

logger = get_logger(__name__)


class ModLLMDM:
    def __init__(self, model_name, model_spec, prompts_dict, player_dict, resp_json_schema, liberal_processing, booking_mandatory_keys) -> None:
        self.model_name = model_name
        self.model_spec = model_spec
        self.prompts_dict = prompts_dict

        self.liberal_processing = liberal_processing
        self.booking_data = {}
        self.slotdata = {}
        self.promptlogs = []
        self.dhistory = []
        self.max_reprobe = 3
        self.cur_reprobe = 0


        self.respformat = resp_json_schema#["schema"]
        self.booking_mandatory_keys = booking_mandatory_keys

        self.player_b = player_dict["modllm_player"]
        self.player_b.history.append({"role": "user", "content": prompts_dict["prompt_b"]})
        self.turn_ss_prompt_player_b = prompts_dict["turn_ss_prompt_b"]
        self.turn_prompt_player_b = prompts_dict["turn_prompt_b"]
        self._create_subsystems(model_name, model_spec, prompts_dict)

        self.liberalcount = {"intent": 0, "slot": 0, "follow": 0, "aggregator": 0}
        self.subsystemnamemap = {"intent_detector": "intent", "slot_extractor": "slot", 
                                 "followup_generator": "follow",
                                 "dbquery_formatter": "dbquery", "booking_formatter": "booking"}
        self.processresp = ProcessFuncCallResp()

    def _create_subsystems(self, model_name, model_spec, prompts_dict):
        self.intentdet = IntentDetector(model_name, model_spec, prompts_dict["intent_detection"])
        self.slotext = SlotExtractor(model_name, model_spec, prompts_dict["slot_extraction"], self.respformat)
        self.followupgen = FollowupGenerator(
            model_name, model_spec, prompts_dict["followup_generation"]
        )
        self.dbqueryformatter = DBQueryFormatter(
            model_name, model_spec, prompts_dict["dbquery_formatter"], self.respformat
        )
        self.bookingformatter = BookingFormatter(
            model_name, model_spec, prompts_dict["booking_formatter"], self.respformat
        )



    def _append_utterance(self, subsystem: str, utterance: str, role: str) -> None:
        """Add an utterance to the history of a player (firstlast specific)."""

        message = utterance
        if isinstance(utterance, dict) or isinstance(utterance, list):
            message = json.dumps(utterance)

        if role == "assistant":
            self.player_b.history.append({"role": role, "content": message})
        else:
            if subsystem is None:
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
            else:
                if utterance:
                    turn_prompt = self.turn_ss_prompt_player_b.replace(
                        "$sub-system", subsystem
                    )
                    turn_prompt += "\n\n" + message
                else:
                    turn_prompt = subsystem
                self.player_b.history.append({"role": role, "content": turn_prompt.strip()})


    def _validate_subsystem(self, nextsubsystem: str) -> bool:
        if nextsubsystem in self.subsystemnamemap:
            self.cur_reprobe = 0
            return True, nextsubsystem
        else:
            if self.liberal_processing:
                for key, value in self.subsystemnamemap.items():
                    if value in nextsubsystem.lower():
                        self.liberalcount[key] += 1
                        self.cur_reprobe = 0
                        return True, key
                if self.cur_reprobe  < self.max_reprobe:
                    self.cur_reprobe += 1
                    return False, "reprobe"
                else:
                    return False, None
        return False, None
    
    def _validate_subsystem_input(self, sub_system: str, taskinput: Dict) -> Dict:
        logger.info(f"Validating Subsystem Input: {sub_system}-> {taskinput} {type(taskinput)}")
        if taskinput is None or isinstance(taskinput, str) or isinstance(taskinput, json.decoder.JSONDecodeError):
            return None
        else:
            if sub_system == "intent_detector":
                if "intent_detection" in taskinput and "domain" in taskinput:
                    return taskinput
                else:
                    return None
            elif sub_system == "slot_extractor":
                if "slot_extraction" in taskinput:
                    return taskinput
                else:
                    return None
            elif sub_system == "followup_generator":
                if "followup_generation" in taskinput:
                    return taskinput
                else:
                    return None
            elif sub_system == "dbquery_formatter":
                if "dbquery_format" in taskinput:
                    return taskinput
                else:
                    return None
            elif sub_system == "booking_formatter":
                if "booking_query" in taskinput:
                    return taskinput
                else:
                    return None
            return taskinput
        

    def run(self, utterance, current_turn: int) -> str:
        """
        The following actions will be done in a loop until the DM module is ready to respond to user request
        1. Feed the user input to the LLM DM
        2. Get the next action from the LLM DM
        3. Call the relevant module with the action
        4. If there is no matching module, probe the LLM DM one more time (total: 2 times)
        5. Go to step 2 and repeat the above steps until the DM module is ready to respond to the user request or the number of probes reaches 5
        """

        subsystem_handlers = {
                    "intent_detector": self.intentdet.run,
                    "slot_extractor": self.slotext.run,
                    "followup_generator": self.followupgen.run,
                    "dbquery_formatter": self.dbqueryformatter.run,
                    "booking_formatter": self.bookformatter.run
                }

        self.promptlogs = []
        self.cur_reprobe = 0
        self.promptlogs.append({"role": "user", "content": f"User Query: {utterance}"})
        self._append_utterance(None, utterance, "user")

        while True:
            prompt, raw_answer, answer = self.player_b(
                self.player_b.history, current_turn, None, self.respformat
            )
            logger.info(f"Player B: Subsystem Flow response\n{answer}")
            self.promptlogs.append({"role": "assistant", "content": f"model response before processing: {answer}"})
            result = cleanupanswer(answer)
            self.promptlogs.append({'role': "modllm", 'content': {'prompt': prompt, 'raw_answer': raw_answer,
                                                                    'answer': result}})
            self._append_utterance(None, result, "assistant")

            if isinstance(result, dict):
                next_subsystem = result.get("next_subsystem", None)
            else:
                next_subsystem = None

            logger.info(f"Player B: Next SubSystem response\n{next_subsystem}")
            if next_subsystem:
                next_subsystem = next_subsystem.lower()
                taskinput = result.get("input_data", None)
                logger.info(f"Player B: Next SubSystem Input\n{taskinput}")
                self.promptlogs.append({"role": f"Input to {next_subsystem}", 'content': f"Input to {next_subsystem} sub-system:\n{json.dumps(taskinput)}"})           

                status, use_subsystem = self._validate_subsystem(next_subsystem)
                logger.info(f"Player B: Subsystem Validation: status - {status}, use_subsystem - {use_subsystem}")

                if not status:
                    if use_subsystem == "reprobe":
                        # Probe the LLM one more time
                        # TODO: Do we need to add any message to the LLM to behave itself?
                        # self._append_utterance(None, answer, "user")
                        logger.error(
                            "No matching sub-system found for the next task. Probing the LLM one more time."
                        )
                        self._append_utterance(
                            "No matching sub-system found for the next task.", None, "user"
                        )                        
                        continue
                    else:
                        errormsg = f"Invalid Subsystem: {next_subsystem}. Cannot continue processing."
                        logger.error(errormsg)
                        #Game Master should treat this as failure and abort the game
                        self.promptlogs.append({"role": "assistant", "content": errormsg})
                        return self.promptlogs, None, errormsg

                usetaskinput = self._validate_subsystem_input(next_subsystem, taskinput)

                if usetaskinput is None:
                    errormsg = f"Invalid Subsystem({use_subsystem}) InputData {taskinput}. Cannot continue processing."
                    logger.error(errormsg)
                    #Game Master should treat this as failure and abort the game
                    return self.promptlogs, None, errormsg


                prompt, raw_response, raw_answer_ss, ss_answer = subsystem_handlers[use_subsystem](usetaskinput, current_turn)
                self.promptlogs.append({"role": f"{use_subsystem}", 'content': {'prompt': prompt, 'raw_answer': raw_response,
                                                                    'answer': f"Sub-system({use_subsystem}) response: {ss_answer}"}})                
                logger.info(f"{use_subsystem} response appending to Player B\n{ss_answer}")
                self._append_utterance(use_subsystem, ss_answer, "user")
                #Adding sleep to reduce the frequencey of calls to the LLM
                time.sleep(0.5)                   
            else:
                # Return the LLM response to user
                logger.info(f"Returning the LLM response to the user\n{result}")
                llm_response, error = self.processresp.run(result)
                if error:
                    self.promptlogs.append({"role": "assistant", "content": f"error while parsing the data: {error}"})

                self.promptlogs.append({'role': "modllm", 'content': {'prompt': prompt, 'raw_answer': raw_answer,
                                                                    'answer': llm_response}})

                return self.promptlogs, raw_answer, llm_response      
