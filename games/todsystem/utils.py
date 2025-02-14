import random
import string
import json
from clemgame import get_logger

logger = get_logger(__name__)

def processgtslots(slots: dict) -> dict:
    modgt_slots = {}
    for domain, data in slots.items():
        domain_lower = domain.lower()
        modgt_slots[domain_lower] = {}
        for key, dvalue in data.items():
            key_lower = key.lower()

            if key_lower not in ["fail_info", "fail_book"]:
                if isinstance(dvalue, dict):
                    modgt_slots[domain_lower][key_lower] = {k.lower(): str(v).lower() for k, v in dvalue.items() if k not in ["invalid", "pre_invalid"]}
                elif isinstance(dvalue, list):
                    modgt_slots[domain_lower][key_lower] = [str(v).lower() for v in dvalue]
    return modgt_slots

def processgenslots(gen_slots: dict) -> dict:
    modgen_slots = {}
    for domain, data in gen_slots.items():
        domain_lower = domain.lower()
        if domain_lower not in modgen_slots:
            modgen_slots[domain_lower] = {}

        for key, value in data.items():
            key_lower = key.lower()
            if domain_lower == "train":
                if key_lower in ["info", "reqt"]:
                    modgen_slots[domain_lower][key_lower] = {k.lower(): str(v).lower() for k, v in value.items()}
                elif key_lower in ["book"]:
                    for k, v in value.items():
                        if k in ["bookpeople", "tickets"]:
                            modgen_slots[domain_lower]["people"] = str(v).lower()
                        else:
                            modgen_slots[domain_lower][k.lower()] = str(v).lower()
                else:
                    if key == "tickets":
                        modgen_slots[domain_lower]["people"] = str(value).lower()
                    else:
                        modgen_slots[domain_lower][key_lower] = str(value).lower()
            elif domain_lower == "restaurant":
                if key_lower in ["info", "reqt"]:
                    modgen_slots[domain_lower][key_lower] = {k.lower(): str(v).lower() for k, v in value.items()}
                elif key_lower in ["book"]:
                    for k, v in value.items():
                        if k == "bookpeople":
                            modgen_slots[domain_lower]["people"] = str(v).lower()
                        elif k == "bookday":
                            modgen_slots[domain_lower]["day"] = str(v).lower()
                        elif k == "booktime":
                            modgen_slots[domain_lower]["time"] = str(v).lower()
                        else:
                            modgen_slots[domain_lower][k.lower()] = str(v).lower()
                else:
                    if key == "bookpeople":
                        modgen_slots[domain_lower]["people"] = str(value).lower()
                    elif key == "bookday":
                        modgen_slots[domain_lower]["day"] = str(value).lower()
                    elif key == "booktime":
                        modgen_slots[domain_lower]["time"] = str(value).lower()
                    else:
                        modgen_slots[domain_lower][key_lower] = str(value).lower()
            elif domain_lower == "hotel":
                if key_lower in ["info", "reqt"]:
                    modgen_slots[domain_lower][key_lower] = {k.lower(): str(v).lower() for k, v in value.items()}
                elif key_lower in ["book"]:
                    for k, v in value.items():
                        if k == "bookpeople":
                            modgen_slots[domain_lower]["people"] = str(v).lower()
                        elif k == "bookday":
                            modgen_slots[domain_lower]["day"] = str(v).lower()
                        elif k == "booktime":
                            modgen_slots[domain_lower]["time"] = str(v).lower()
                        elif k == "bookstay":
                            modgen_slots[domain_lower]["stay"] = str(v).lower()
                        else:
                            modgen_slots[domain_lower][k.lower()] = str(v).lower()
                else:
                    if key == "bookpeople":
                        modgen_slots[domain_lower]["people"] = str(value).lower()
                    elif key == "bookday":
                        modgen_slots[domain_lower]["day"] = str(value).lower()
                    elif key == "booktime":
                        modgen_slots[domain_lower]["time"] = str(value).lower()
                    elif key == "bookstay":
                        modgen_slots[domain_lower]["stay"] = str(value).lower()
                    else:
                        modgen_slots[domain_lower][key_lower] = str(value).lower()
            else:
                modgen_slots[domain_lower][key_lower] = str(value).lower()

    return modgen_slots

def cleanupanswer(prompt_answer: str) -> str:
    """Clean up the answer from the LLM DM."""
    #if "```json" in prompt_answer:
    prompt_answer = prompt_answer.replace("```json", "").replace("```", "")
    try:
        prompt_answer = json.loads(prompt_answer)
        #return prompt_answer
    except Exception as error:
        logger.error(f"Error in cleanupanswer: {error}")
    return prompt_answer
  

def generate_reference_number(length=6):
    characters = string.ascii_uppercase + string.digits  # Uppercase letters and digits
    random_string = ''.join(random.choices(characters, k=length))
    return random_string