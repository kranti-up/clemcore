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
from games.dmsystem_modular_llm.dbqueryformatter import DBQueryFormatter
from games.dmsystem_modular_llm.bookingformatter import BookingFormatter

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
        self.dbqueryformatter = DBQueryFormatter(model_name, game_data["prompts_dict"]["dbquery_formatter"])
        self.bookformatter = BookingFormatter(model_name, game_data["prompts_dict"]["booking_formatter"])

        self.liberalcount = {"intent": 0, "slot": 0, "follow": 0, "aggregator": 0}
        self.subsystemnamemap = {"intent_detector": "intent", "slot_extractor": "slot", 
                                 "followup_generator": "follow",
                                 "dbquery_formatter": "dbquery", "booking_formatter": "booking"}


    def _append_utterance(self, subsystem: str, utterance: str, role: str) -> None:
        """Add an utterance to the history of a player (firstlast specific)."""

        message = utterance
        if isinstance(utterance, dict) or isinstance(utterance, list):
            message = json.dumps(utterance)


        if role == "assistant":
            self.player_b.history.append({"role": role, "content": message})
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
                    "dbquery_formatter": self.dbqueryformatter.run,
                    "booking_formatter": self.bookformatter.run
                }

        while True:
            prompt, raw_answer, answer = self.player_b(
                self.player_b.history, current_turn, self.respformat
            )
            logger.info(f"Player B: Subsystem Flow response\n{answer}")

            answer = cleanupanswer(answer)
            self._append_utterance(None, answer, "assistant")

            try:
                result = json.loads(answer)
            except Exception as e:
                result = answer

            if isinstance(result, dict):
                next_subsystem = result.get("next_subsystem", None)
            else:
                next_subsystem = None

            logger.info(f"Player B: Next SubSystem response\n{next_subsystem}")
            if next_subsystem:
                next_subsystem = next_subsystem.lower()
                taskinput = result.get("input_data", None)
                logger.info(f"Player B: Next SubSystem Input\n{taskinput}")

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
                        logger.error(f"Invalid Subsystem: {next_subsystem}. Cannot continue processing.")
                        #Game Master should treat this as failure and abort the game
                        return prompt, None, None

                usetaskinput = self._validate_subsystem_input(taskinput)

                if usetaskinput is None:
                    logger.error(f"Invalid Subsystem InputData {taskinput}. Cannot continue processing.")
                    #Game Master should treat this as failure and abort the game
                    return prompt, None, None


                ss_response = subsystem_handlers[use_subsystem](usetaskinput, current_turn)
                logger.info(f"{use_subsystem} response appending to Player B\n{ss_response}")
                self._append_utterance(use_subsystem, ss_response, "user")
                #Adding sleep to reduce the frequencey of calls to the LLM
                time.sleep(3)                   
            else:
                # Return the LLM response to user
                logger.info(f"Returning the LLM response to the user\n{answer}")
                return prompt, raw_answer, answer      
