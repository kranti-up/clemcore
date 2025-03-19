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

            #if key_lower not in ["fail_info", "fail_book"]:
            if isinstance(dvalue, dict):
                modgt_slots[domain_lower][key_lower] = {k.lower(): str(v).lower() for k, v in dvalue.items() if k not in ["invalid", "pre_invalid"]}
            elif isinstance(dvalue, list):
                modgt_slots[domain_lower][key_lower] = [str(v).lower() for v in dvalue]
    return modgt_slots


def preparegenslots(gen_slots: dict) -> dict:
    base_schema = {'hotel': {'info': ['internet', 'type', 'name', 'area', 'parking', 'pricerange', 'stars'],
                             'book': ['stay', 'day', 'people'],
                             'reqt': ['phone', 'area', 'postcode', 'address']},
                   'restaurant': {'info': ['food', 'name', 'pricerange', 'area'],
                                  'book': ['time', 'day', 'people'],
                                  'reqt': ['phone', 'postcode', 'address']},
                   'train': {'info': ['destination', 'departure', 'arriveby', 'leaveat', 'day'],
                             'book': ['people'],
                             'reqt': ['trainid']},
                   'attraction': {'info': ['name', 'area', 'type'],
                                   'book': [],
                                   'reqt': ['entrance fee', 'phone', 'postcode', 'address']},
                   'taxi': {'info': ['arriveby', 'leaveat'],
                            'book': [],
                            'reqt': ['phone', 'car type']}}

    gprocessed_slots = {}    
    for domain in gen_slots:
        if domain not in base_schema:
            logger.error(f"Domain {domain} not in the base schema: {base_schema.keys()}")
            return None
        gprocessed_slots[domain] = {}

        for key in gen_slots[domain]:
            keyfound = False

            use_key = key.lower()
            if domain == "train":
                if use_key in ["tickets", "bookpeople"]:
                    use_key = "people"
                elif use_key in ["train id"]:
                    use_key = "trainid"



            for stype in ["info", "book", "reqt"]:
                if use_key in base_schema[domain][stype]:
                    if stype not in gprocessed_slots[domain]:
                        gprocessed_slots[domain][stype] = {}


                    gprocessed_slots[domain][stype][use_key] = str(gen_slots[domain][key]).lower()
                    keyfound = True
                    break
            if not keyfound:
                print(f"Key {key} not found in the base schema for domain {domain}")

    return gprocessed_slots
    

def processgenslots(gen_slots: dict) -> dict:
    modgen_slots = {}
    for domain, data in gen_slots.items():
        domain_lower = domain.lower()
        if domain_lower not in modgen_slots:
            modgen_slots[domain_lower] = {}

        for key, value in data.items():
            key_lower = key.lower()
            if key_lower not in modgen_slots[domain_lower]:
                modgen_slots[domain_lower][key_lower] = {}
            if domain_lower == "train":
                if key_lower in ["info"]:
                    for k, v in value.items():
                        if isinstance(v, dict):
                            modgen_slots[domain_lower][key_lower][k.lower()] = str(list(v.values())[1]).lower()
                        else:
                            modgen_slots[domain_lower][key_lower][k.lower()] = str(v).lower()
                elif key_lower in ["reqt"]:
                    for k, v in value.items():
                        if isinstance(v, list):
                            modgen_slots[domain_lower][key_lower][k.lower()] = [str(i).lower() for i in v]
                        else:
                            modgen_slots[domain_lower][key_lower][k.lower()] = str(v).lower()

                #if key_lower in ["info", "reqt"]:
                #    modgen_slots[domain_lower][key_lower] = {k.lower(): str(v).lower() for k, v in value.items()}
                elif key_lower in ["book"]:
                    for k, v in value.items():
                        if k in ["bookpeople", "tickets"]:
                            modgen_slots[domain_lower][key_lower]["people"] = str(v).lower()
                        else:
                            modgen_slots[domain_lower][key_lower][k.lower()] = str(v).lower()
                else:
                    if key == "tickets":
                        modgen_slots[domain_lower][key_lower]["people"] = str(value).lower()
                    else:
                        modgen_slots[domain_lower][key_lower] = str(value).lower()
            elif domain_lower == "restaurant":
                if key_lower in ["info"]:
                    for k, v in value.items():
                        if isinstance(v, dict):
                            modgen_slots[domain_lower][key_lower][k.lower()] = str(list(v.values())[1]).lower()
                        else:
                            modgen_slots[domain_lower][key_lower][k.lower()] = str(v).lower()

                elif key_lower in ["reqt"]:
                    for k, v in value.items():
                        if isinstance(v, list):
                            modgen_slots[domain_lower][key_lower][k.lower()] = [str(i).lower() for i in v]
                        else:
                            modgen_slots[domain_lower][key_lower][k.lower()] = str(v).lower()

                #if key_lower in ["info", "reqt"]:
                #    modgen_slots[domain_lower][key_lower] = {k.lower(): str(v).lower() for k, v in value.items()}
                elif key_lower in ["book"]:
                    for k, v in value.items():
                        if k == "bookpeople":
                            modgen_slots[domain_lower][key_lower]["people"] = str(v).lower()
                        elif k == "bookday":
                            modgen_slots[domain_lower][key_lower]["day"] = str(v).lower()
                        elif k == "booktime":
                            modgen_slots[domain_lower][key_lower]["time"] = str(v).lower()
                        else:
                            modgen_slots[domain_lower][key_lower][k.lower()] = str(v).lower()
                else:
                    if key == "bookpeople":
                        modgen_slots[domain_lower][key_lower]["people"] = str(value).lower()
                    elif key == "bookday":
                        modgen_slots[domain_lower][key_lower]["day"] = str(value).lower()
                    elif key == "booktime":
                        modgen_slots[domain_lower][key_lower]["time"] = str(value).lower()
                    else:
                        modgen_slots[domain_lower][key_lower][key.lower()] = str(value).lower()
            elif domain_lower == "hotel":
                if key_lower in ["info"]:
                    for k, v in value.items():
                        if isinstance(v, dict):
                            modgen_slots[domain_lower][key_lower][k.lower()] = str(list(v.values())[1]).lower()
                        else:
                            modgen_slots[domain_lower][key_lower][k.lower()] = str(v).lower()

                elif key_lower in ["reqt"]:
                    for k, v in value.items():
                        if isinstance(v, list):
                            modgen_slots[domain_lower][key_lower][k.lower()] = [str(i).lower() for i in v]
                        else:
                            modgen_slots[domain_lower][key_lower][k.lower()] = str(v).lower()


                #if key_lower in ["info", "reqt"]:
                #    modgen_slots[domain_lower][key_lower] = {k.lower(): str(v).lower() for k, v in value.items()}
                elif key_lower in ["book"]:
                    for k, v in value.items():
                        if k == "bookpeople":
                            modgen_slots[domain_lower][key_lower]["people"] = str(v).lower()
                        elif k == "bookday":
                            modgen_slots[domain_lower][key_lower]["day"] = str(v).lower()
                        elif k == "booktime":
                            modgen_slots[domain_lower][key_lower]["time"] = str(v).lower()
                        elif k == "bookstay":
                            modgen_slots[domain_lower][key_lower]["stay"] = str(v).lower()
                        else:
                            modgen_slots[domain_lower][key_lower][k.lower()] = str(v).lower()
                else:
                    if key == "bookpeople":
                        modgen_slots[domain_lower][key_lower]["people"] = str(value).lower()
                    elif key == "bookday":
                        modgen_slots[domain_lower][key_lower]["day"] = str(value).lower()
                    elif key == "booktime":
                        modgen_slots[domain_lower][key_lower]["time"] = str(value).lower()
                    elif key == "bookstay":
                        modgen_slots[domain_lower][key_lower]["stay"] = str(value).lower()
                    else:
                        modgen_slots[domain_lower][key_lower][key.lower()] = str(value).lower()
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
        return error
    return prompt_answer
  

def generate_reference_number(length=6):
    characters = string.ascii_uppercase + string.digits  # Uppercase letters and digits
    random_string = ''.join(random.choices(characters, k=length))
    return random_string


if __name__ == "__main__":
    gen_slots = {"taxi": {"arriveBy": "15:00"}}
    print(processgenslots(gen_slots))
