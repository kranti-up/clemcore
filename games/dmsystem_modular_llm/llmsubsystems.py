import time
import copy
from typing import Dict
import json

import clemgame
from clemgame import get_logger
from games.dmsystem_monolithic_llm.utils import cleanupanswer
from games.dmsystem_modular_llm.players import ModularLLMSpeaker
from games.dmsystem_modular_llm.intentdetector import IntentDetector
from games.dmsystem_modular_llm.slotextractor import SlotExtractor
from games.dmsystem_modular_llm.followupgenerator import FollowupGenerator
from games.dmsystem_modular_llm.bookingaggregator import BookingAggregator

logger = get_logger(__name__)


class LLMSubSystems:
    def __init__(
        self, model_name: str, game_data: Dict, player: object) -> None:
        self.model_name = model_name
        self.game_data = game_data
        self.respformat = game_data["json_schema"]
        self.player_b = player

        self.turn_ss_prompt_player_b = game_data["prompts_dict"]["turn_ss_prompt_b"]

        self.liberal_processing = game_data["liberal_processing"]

        self.intentdet = IntentDetector(model_name, game_data["prompts_dict"]["intent_detection"])
        self.slotext = SlotExtractor(model_name, game_data["prompts_dict"]["slot_extraction"])
        self.followupgen = FollowupGenerator(model_name, game_data["prompts_dict"]["followup_generation"])
        #self.bookaggregator = BookingAggregator(model_name, prompts_dict["booking_aggregator"])

        self.liberalcount = {"intent": 0, "slot": 0, "follow": 0, "aggregator": 0}
        self.subsystemnamemap = {"intent_detector": "intent", "slot_extractor": "slot", 
                                 "followup_generator": "follow"}#, "booking_aggregator": "aggregator"}


    def _append_utterance(self, subsystem: str, utterance: str, role: str) -> None:
        """Add an utterance to the history of a player (firstlast specific)."""
        if role == "assistant":
            if isinstance(utterance, dict) or isinstance(utterance, list):
                self.player_b.history.append(
                    {"role": role, "content": json.dumps(utterance)}
                )
            else:
                self.player_b.history.append({"role": role, "content": utterance})
        else:
            if utterance:
                turn_prompt = self.turn_ss_prompt_player_b.replace(
                    "$sub-system", subsystem
                )
                if isinstance(utterance, dict) or isinstance(utterance, list):
                    turn_prompt += "\n\n" + json.dumps(utterance)
                else:
                    turn_prompt += "\n\n" + utterance
            else:
                turn_prompt = subsystem
            self.player_b.history.append({"role": role, "content": turn_prompt.strip()})
            # print(self.player_b.history[-1])
            # input()


    def _validate_subsystem(self, nextsubsystem: str) -> bool:
        if nextsubsystem in self.subsystemnamemap:
            return True, nextsubsystem
        else:
            if self.liberal_processing:
                for key, value in self.subsystemnamemap.items():
                    if value in nextsubsystem.lower():
                        self.liberalcount[key] += 1
                        return True, key
                return False, "reprobe"
        return False, None
    
    def _validate_subsystem_input(self, taskinput: Dict) -> Dict:
        if taskinput is None:
            return {}
        elif all(isinstance(value, dict) for value in taskinput.values()):
            return {}
        else:
            return taskinput
        

    def run(self, current_turn: int) -> str:
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
                    #"booking_aggregator": self.bookaggregator.run
                }        
        num_probes = 0

        while True:
            # print(f'2.1 Calling player B, num_probes: {num_probes}')#\n{self.player_b.history}')
            # input()
            prompt, raw_answer, answer = self.player_b(
                self.player_b.history, current_turn, self.respformat
            )
            logger.error(f"Player B: Subsystem Flow response\n{answer}")
            num_probes += 1
            answer = cleanupanswer(answer)
            # print('2.2 DM System Output\n',answer)
            # input()
            self._append_utterance(None, answer, "assistant")

            try:
                result = json.loads(answer)
            except Exception as e:
                result = answer

            # print(f'2.3 Result = {result} TypeR = {type(result)} TypeA = {type(answer)}')
            if isinstance(result, dict):
                next_subsystem = result.get("next_subsystem", None)
            else:
                next_subsystem = None

            # print(f'2.4 Next SubSystem: {next_subsystem}')#, type: {type(result)}, result: {result}')
            logger.error(f"Player B: Next SubSystem response\n{next_subsystem}")
            if next_subsystem:
                next_subsystem = next_subsystem.lower()
                taskinput = result.get("input_data", None)
                logger.error(f"Player B: Next SubSystem Input\n{taskinput}")

                status, use_subsystem = self._validate_subsystem(next_subsystem)
                logger.error(f"Player B: Subsystem Validation: status - {status}, use_subsystem - {use_subsystem}")

                if not status:
                    if use_subsystem == "reprobe":
                        # Probe the LLM one more time
                        # TODO: Do we need to add any message to the LLM to behave itself?
                        # self._append_utterance(None, answer, "user")
                        logger.error(
                            "No matching sub-system found for the next task. Probing the LLM one more time."
                        )
                        # print("2.5 No matching sub-system found for the next task. Probing the LLM one more time.")
                        self._append_utterance(
                            "No matching sub-system found for the next task.", None, "user"
                        )                        

                    else:
                        logger.error(f"Invalid Subsystem: {next_subsystem}. Cannot continue processing.")
                        #Game Master should treat this as failure and abort the game
                        #TODO: Having None for prompt, raw_answer and answer is not a good idea. Need to handle this properly
                        return None, None, None

                usetaskinput = self._validate_subsystem_input(taskinput)

                if usetaskinput is None:
                    logger.error(f"Invalid Subsystem InputData {taskinput}. Cannot continue processing.")
                    #Game Master should treat this as failure and abort the game
                    #TODO: Having None for prompt, raw_answer and answer is not a good idea. Need to handle this properly
                    return None, None, None


                ss_response = subsystem_handlers[use_subsystem](usetaskinput, current_turn)
                logger.error(f"{use_subsystem} response appending to Player B\n{ss_response}")
                self._append_utterance(use_subsystem, ss_response, "user")
                #Adding sleep to reduce the frequencey of calls to the LLM
                time.sleep(3)                   
            else:
                # Return the LLM response to user
                # print(f'2. Returning the LLM response to user:\n{answer}')
                # input()
                # print(f"2.6 Returning the LLM response to the user:\n{answer}")
                # input()
                logger.error(f"Returning the LLM response to the user\n{answer}")
                return prompt, raw_answer, answer      
