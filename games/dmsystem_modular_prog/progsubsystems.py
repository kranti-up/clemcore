import time
import copy
from typing import Dict
import json

import clemgame
from clemgame import get_logger
from games.dmsystem_monolithic_llm.utils import cleanupanswer
from games.dmsystem_modular_prog.players import ModularProgSpeaker
from games.dmsystem_modular_prog.intentdetector import IntentDetector
from games.dmsystem_modular_prog.slotextractor import SlotExtractor
from games.dmsystem_modular_prog.followupgenerator import FollowupGenerator
from games.dmsystem_modular_prog.dbqueryformatter import DBQueryFormatter
from games.dmsystem_modular_prog.bookingformatter import BookingFormatter

logger = get_logger(__name__)


class ProgSubSystems:
    def __init__(self, model_name: str, game_data: Dict, player: object) -> None:
        self.model_name = model_name
        self.player_b = player
        self.booking_data = {}
        self._save_game_data(game_data)
        self._create_subsystems(model_name, game_data["prompts_dict"])
        self.usergoal = None
        self.current_state = None
        self.slotdata = {}
        self.dhistory = []

        self.turn_ss_prompt_player_b = game_data["prompts_dict"]["turn_ss_prompt_b"]
        self.liberalcount = {"intent": 0, "slot": 0, "follow": 0, "aggregator": 0}
        self.subsystemnamemap = {
            "intent_detector": "intent",
            "slot_extractor": "slot",
            "followup_generator": "follow",
            "dbquery_formatter": "dbqueryformatter",
        }
        logger.info(f"ProgSubSystems __init__ done")

    def _save_game_data(self, game_data):
        self.game_data = game_data
        self.respformat = game_data["json_schema"]
        self.db_query_slots = self.respformat["schema"]["properties"]["details"][
            "oneOf"
        ][1]["properties"]
        self.booking_query_slots = self.respformat["schema"]["properties"]["details"][
            "oneOf"
        ][2]["properties"]
        self.booking_keys = list(self.booking_query_slots.keys())
        self.liberal_processing = game_data["liberal_processing"]

    def _create_subsystems(self, model_name, prompts_dict):
        self.intentdet = IntentDetector(model_name, prompts_dict["intent_detection"])
        self.slotext = SlotExtractor(model_name, prompts_dict["slot_extraction"])
        self.followupgen = FollowupGenerator(
            model_name, prompts_dict["followup_generation"]
        )
        self.dbqueryformatter = DBQueryFormatter(
            model_name, prompts_dict["dbquery_formatter"]
        )
        self.bookingformatter = BookingFormatter(
            model_name, prompts_dict["booking_formatter"]
        )

    def _append_utterance(self, subsystem: str, utterance: str, role: str) -> None:
        """Add an utterance to the history of a player (firstlast specific)."""

        if isinstance(utterance, dict) or isinstance(utterance, list):
            utterance = json.dumps(utterance)

        add_data = utterance

        if role == "user":
            add_data = subsystem
            if utterance:
                turn_prompt = self.turn_ss_prompt_player_b.replace(
                    "$sub-system", subsystem
                )
                add_data = turn_prompt + "\n\n" + utterance

        self.player_b.history.append({"role": role, "content": add_data.strip()})

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

    def _prepare_subsystem_input(self, taskinput: Dict, next_subsystem: str) -> Dict:
        return json.dumps({"next_subsystem": next_subsystem, "input_data": taskinput})

    def _validate_subsystem_input(self, taskinput: Dict) -> Dict:
        logger.info(f"Validating Subsystem Input: {taskinput} {type(taskinput)}")
        if taskinput is None:
            return {}
        # elif all(isinstance(value, dict) for value in taskinput.values()):
        #    return {}
        else:
            return taskinput

    def _getquery_type(self, data):
        if "USER REQUEST:" in self.player_b.history[-1]["content"]:
            split_query = "USER REQUEST:"
            query_type = "user-request"
        elif "DATABASE RETRIEVAL RESULTS:" in self.player_b.history[-1]["content"]:
            split_query = "DATABASE RETRIEVAL RESULTS:"
            query_type = "db-retrieval"
        elif "BOOKING VALIDATION STATUS:" in self.player_b.history[-1]["content"]:
            split_query = "BOOKING VALIDATION STATUS:"
            query_type = "booking-validation"

        user_request = (
            self.player_b.history[-1]["content"].split(split_query)[1].strip()
        )

        return query_type, user_request

    def _call_subsystem(self, sub_system, taskinput: Dict, current_turn: int):
        subsystem_handlers = {
            "intent_detector": self.intentdet,
            "slot_extractor": self.slotext,
            "followup_generator": self.followupgen,
            "dbquery_formatter": self.dbqueryformatter,
            "booking_formatter": self.bookingformatter,
        }
        logger.info(
            f"Calling Subsystem: {sub_system} with taskinput: {taskinput}, Current Turn: {current_turn}"
        )
        ss_data = self._prepare_subsystem_input(taskinput, sub_system)
        self._append_utterance(None, ss_data, "assistant")
        ss_answer = subsystem_handlers[sub_system].run(taskinput, current_turn)
        # subsystem_handlers[sub_system].clear_history()
        logger.info(f"Subsystem Answer: {ss_answer}, {type(ss_answer)}")
        self._append_utterance(sub_system, ss_answer, "user")
        usetaskinput = self._validate_subsystem_input(ss_answer)

        if usetaskinput is None:
            logger.error(
                f"Invalid Subsystem InputData {ss_answer}. Cannot continue processing."
            )
            # Game Master should treat this as failure and abort the game
            # TODO: Having None for prompt, raw_answer and answer is not a good idea. Need to handle this properly
            return None
        # Adding sleep to reduce the frequencey of calls to the LLM
        time.sleep(0.5)
        return usetaskinput

    def _prepare_gm_response(self, status, details):
        prompt = self.player_b.history
        dmanswer = {
            "status": status,
            "details": details,
        }
        raw_answer = {
            "model": self.model_name.model_spec["model_name"],
            "choices": [{"message": {"role": "user", "content": dmanswer}}],
        }

        logger.info(
            f"Returning to GM : {dmanswer} {self.model_name} {type(self.model_name)}"
        )
        return prompt, raw_answer, json.dumps(dmanswer)

    def _isbookingready(self, query_type, user_request):
        ext_data = self.slotdata
        booking_required = self.booking_keys
        for key in booking_required:
            if key not in ext_data:
                return False
        return True

    def _updateslots(self, curslots, dbformatslots):
        for slot in curslots:
            if slot in dbformatslots:
                curslots[slot] = dbformatslots[slot]

    def run(self, current_turn: int) -> str:
        """
        The following actions will be done in a loop until the DM module is ready to respond to user request
        1. Feed the user input to the LLM DM
        2. Get the next action from the LLM DM
        3. Call the relevant module with the action
        4. If there is no matching module, probe the LLM DM one more time (total: 2 times)
        5. Go to step 2 and repeat the above steps until the DM module is ready to respond to the user request or the number of probes reaches 5
        """
        query_type, user_request = self._getquery_type(
            self.player_b.history[-1]["content"]
        )
        logger.info(
            f"Query Type: {query_type}, User Request: {user_request} Current Turn: {current_turn}"
        )
        if current_turn == 1:
            if self.usergoal is None:
                self.usergoal = user_request
                self.current_state = "user-request"
                # self.dhistory.append({"role": "user", "content": user_request})

        while True:
            taskinput = {"user_request": user_request}
            if self.dhistory:
                taskinput["dialog_history"] = self.dhistory
            intent_answer = self._call_subsystem(
                "intent_detector", taskinput, current_turn
            )
            logger.info(f"Intent Answer: {intent_answer} {type(intent_answer)}")
            if intent_answer is None:
                return None, None, None

            self.dhistory.append(
                {
                    "role": "user",
                    "user_request": user_request,
                    "intent": intent_answer["intent_detection"],
                }
            )

            if query_type == "user-request":
                slot_answer = self._call_subsystem(
                    "slot_extractor", taskinput, current_turn
                )
                logger.info(f"Slot Answer: {slot_answer}")
                if slot_answer is None:
                    return None, None, None

                if slot_answer["slot_extraction"]:
                    self.slotdata.update(slot_answer["slot_extraction"])

            intent_detection = intent_answer["intent_detection"]
            if intent_detection == "booking-request":
                # self.booking_data.update(slot_answer["slot_extraction"])
                ext_slots = self.slotdata
                logger.info(f"ext_slots: {ext_slots}")

                missed_slots = list(
                    set(self.booking_query_slots.keys()) - set(ext_slots.keys())
                )

                if missed_slots:
                    logger.info(f"Missed Slots: {missed_slots}")
                    taskinput = {
                        "extracted slots": self.slotdata,
                        "missing_booking_slots": missed_slots,
                    }
                    if self.dhistory:
                        taskinput["dialog_history"] = self.dhistory
                    followup_answer = self._call_subsystem(
                        "followup_generator", taskinput, current_turn
                    )
                    logger.info(
                        f"In booking-request: Followup Answer: {followup_answer}"
                    )
                    if followup_answer is None:
                        return None, None, None
                    self.current_state = "booking-request"
                    self.dhistory.append(
                        {
                            "role": "assistant",
                            "intent": "follow-up",
                            "response": followup_answer["followup_generation"],
                        }
                    )
                    return self._prepare_gm_response(
                        "follow-up", followup_answer["followup_generation"]
                    )
                else:
                    logger.info(f"Information ready for booking {ext_slots}")
                    taskinput = {"extracted data": ext_slots}
                    bookingformatter_answer = self._call_subsystem(
                        "booking_formatter", taskinput, current_turn
                    )
                    logger.info(
                        f"After Booking Formatter: bookingformatter_answer = {bookingformatter_answer}"
                    )
                    if bookingformatter_answer is None:
                        return None, None, None

                    self.current_state = "validate-booking"
                    self.dhistory.append(
                        {"role": "assistant", "intent": "validate-booking",
                         "response": bookingformatter_answer["booking_query"]}
                    )
                    # self.dhistory[-1].update({"assistant": "validate-booking"})
                    return self._prepare_gm_response(
                        "validate-booking", bookingformatter_answer["booking_query"]
                    )
            elif intent_detection in ["booking-success", "booking-failure"]:
                self.dhistory.append(
                    {
                        "role": "user",
                        "intent": intent_detection,
                        "response": user_request,
                    }
                )

                taskinput = {"booking_confirmation_status": user_request}
                if self.dhistory:
                    taskinput["dialog_history"] = self.dhistory



                followup_answer = self._call_subsystem(
                    "followup_generator", taskinput, current_turn
                )
                logger.info(
                    f"After booking success/failure: followup_answer = {followup_answer}"
                )
                if followup_answer is None:
                    return None, None, None

                self.current_state = intent_detection
                self.dhistory.append(
                    {
                        "role": "assistant",
                        "intent": "follow-up",
                        "response": followup_answer["followup_generation"],
                    }
                )
                # self.dhistory[-1].update({"assistant": followup_answer["followup_generation"]})
                return self._prepare_gm_response(
                    "follow-up", followup_answer["followup_generation"]
                )

            elif intent_detection == "dbretrieval-request":
                taskinput = {"extracted data": self.slotdata}
                dbqueryformatter_answer = self._call_subsystem(
                    "dbquery_formatter", taskinput, current_turn
                )
                logger.info(
                    f"After DB Formatter: dbqueryformatter_answer = {dbqueryformatter_answer}"
                )
                if dbqueryformatter_answer is None:
                    return None, None, None

                self._updateslots(
                    self.slotdata, dbqueryformatter_answer["dbquery_format"]
                )
                self.current_state = "db-query"
                self.dhistory.append({"role": "assistant", "intent": "db-query",
                                      "response": dbqueryformatter_answer["dbquery_format"]})
                # self.dhistory[-1].update({"assistant": "db-query"})
                return self._prepare_gm_response(
                    "db-query", dbqueryformatter_answer["dbquery_format"]
                )

            elif intent_detection == "dbretrieval-success":
                # Success in fetching the DB response
                # The answer could be a list of results or a single result
                # Pass the results to follow-up generator to generate the follow-up
                self.dhistory.append(
                    {
                        "role": "user",
                        "intent": intent_detection,
                        "response": "fetched data from DB", #Skipping adding DB results as they are available in taskinput
                    }
                )

                taskinput = {
                    "user_request": self.usergoal,
                    "extracted data": self.slotdata,
                    "required data for booking": self.booking_keys,
                    "db_results": user_request,
                }

                if self.dhistory:
                    taskinput["dialog_history"] = self.dhistory
                followup_answer = self._call_subsystem(
                    "followup_generator", taskinput, current_turn
                )
                logger.info(f"After DB success: followup_answer = {followup_answer}")
                if followup_answer is None:
                    return None, None, None

                self.dhistory.append(
                    {
                        "role": "assistant",
                        "intent": "follow-up",
                        "response": followup_answer["followup_generation"],
                    }
                )
                # self.dhistory[-1].update({"assistant": followup_answer["followup_generation"]})
                return self._prepare_gm_response(
                    "follow-up", followup_answer["followup_generation"]
                )

            elif intent_detection == "dbretrieval-failure":
                # Failure in fetching the DB response
                self.dhistory.append(
                    {
                        "role": "user",
                        "intent": intent_detection,
                        "response": user_request,
                    }
                )

                taskinput = {"missing data for db retrieval": user_request}
                if self.dhistory:
                    taskinput["dialog_history"] = self.dhistory

                followup_answer = self._call_subsystem(
                    "followup_generator", taskinput, current_turn
                )
                logger.info(f"After DB failure: followup_answer = {followup_answer}")
                if followup_answer is None:
                    return None, None, None

                self.dhistory.append(
                    {
                        "role": "assistant",
                        "intent": "follow-up",
                        "response": followup_answer["followup_generation"],
                    }
                )
                # self.dhistory[-1].update({"assistant": followup_answer["followup_generation"]})
                return self._prepare_gm_response(
                    "follow-up", followup_answer["followup_generation"]
                )
            else:
                isbookingready = self._isbookingready(query_type, user_request)
                if isbookingready:
                    logger.info(f"Information ready for booking {self.slotdata}")

                    taskinput = {"extracted data": self.slotdata}
                    bookingformatter_answer = self._call_subsystem(
                        "booking_formatter", taskinput, current_turn
                    )
                    logger.info(
                        f"After Booking Formatter: bookingformatter_answer = {bookingformatter_answer}"
                    )
                    if bookingformatter_answer is None:
                        return None, None, None

                    self.dhistory.append(
                        {"role": "assistant", "intent": "booking_query",
                         "response": bookingformatter_answer["booking_query"]}
                    )
                    return self._prepare_gm_response(
                        "validate-booking", bookingformatter_answer["booking_query"]
                    )

                taskinput = {
                    "user request": user_request,
                    "extracted data": self.slotdata,
                    "required data for booking": self.booking_keys,
                }

                if self.dhistory:
                    taskinput["dialog_history"] = self.dhistory

                followup_answer = self._call_subsystem(
                    "followup_generator", taskinput, current_turn
                )
                logger.info(f"followup_answer = {followup_answer}")
                if followup_answer is None:
                    return None, None, None

                self.dhistory.append(
                    {
                        "role": "assistant",
                        "intent": "follow-up",
                        "response": followup_answer["followup_generation"],
                    }
                )
                # self.dhistory[-1].update({"assistant": followup_answer["followup_generation"]})
                return self._prepare_gm_response(
                    "follow-up", followup_answer["followup_generation"]
                )
