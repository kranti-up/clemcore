import json

from pydantic import BaseModel, Field
from typing import Optional, Literal, Union
from clemgame import get_logger

logger = get_logger(__name__)

class RestaurantDB(BaseModel):
    """Represents valid restaurant search slots."""
    food: Optional[str] = None
    area: Optional[str] = Field(None, pattern="^(centre|north|east|west|south)$")
    pricerange: Optional[str] = Field(None, pattern="^(cheap|moderate|expensive)$")
    name: Optional[str] = None

class RestaurantBook(BaseModel):
    """Represents restaurant booking details."""
    people: Optional[str] = Field(None, pattern="^(1|2|3|4|5|6|7|8)$")
    day: Optional[str] = Field(None, pattern="^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$")
    time: Optional[str] = None  # 24-hour format
    postcode: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None    

class Condition(BaseModel):
    """Represents a conditional field for queries (e.g., stars >= 3)."""
    operator: str  # Allowed: '=', '>=', '<=', '>', '<'
    value: int

class HotelDB(BaseModel):
    """Represents valid hotel search slots."""
    area: Optional[str] = Field(None, pattern="^(centre|north|east|west|south)$")
    pricerange: Optional[str] = Field(None, pattern="^(cheap|moderate|expensive)$")
    type: Optional[str] = Field(None, pattern="^(hotel|guesthouse)$")
    internet: Optional[str] = Field(None, pattern="^(yes|no)$")
    parking: Optional[str] = Field(None, pattern="^(yes|no)$")
    name: Optional[str] = None
    stars: Optional[Condition] = None

class HotelBook(BaseModel):
    """Represents hotel booking details."""
    people: Optional[str] = Field(None, pattern="^(1|2|3|4|5|6|7|8)$")
    day: Optional[str] = Field(None, pattern="^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$")
    stay: Optional[str] = Field(None, pattern="^(1|2|3|4|5|6|7|8)$")
    postcode: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class AttractionDB(BaseModel):
    """Represents valid hotel search slots."""
    area: Optional[str] = Field(None, pattern="^(centre|north|east|west|south)$")
    type: Optional[str] = Field(None, pattern="^(museum|entertainment|college|nightclub|swimming pool|multiple sports|architecture|cinema|boat|theatre|concert hall|park|local site|hotspot|church|special)$")
    name: Optional[str] = None

class AttractionBook(BaseModel):
    """Represents restaurant booking details."""
    postcode: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    entrance_fee: Optional[str] = None

class TrainDB(BaseModel):
    """Represents valid hotel search slots."""
    destination: Optional[str] = None
    departure: Optional[str] = None
    day: Optional[str] = Field(None, pattern="^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$")
    arriveby: Optional[Condition] = None    
    leaveat: Optional[Condition] = None  


class TrainBook(BaseModel):
    """Represents hotel booking details."""
    people: Optional[str] = Field(None, pattern="^(1|2|3|4|5|6|7|8)$")
    trainid: Optional[str] = None    


class TaxiDB(BaseModel):
    """Represents valid hotel search slots."""
    arriveby: Optional[Condition] = None    
    leaveat: Optional[Condition] = None   

class TaxiBook(BaseModel):
    """Represents restaurant booking details."""
    phone: Optional[str] = None
    car_type: Optional[str] = None   


class LLMResponse(BaseModel):
    """Represents the final structured response from the system."""
    status: Literal["follow-up", "db-query", "validate-booking"]
    domain: Literal["restaurant", "hotel", "flight"]
    details: Union[
        str, 
        RestaurantDB, 
        RestaurantBook, 
        HotelDB, 
        HotelBook,
        AttractionDB,
        AttractionBook,
        TrainDB,
        TrainBook,
        TaxiDB,
        TaxiBook
    ]


class ProcessFuncCallResp:

    def __init_(self):
        pass


    def run(self, response):
        logger.info(f"Answer from the model: {response}, {type(response)}")
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except Exception as error:
                logger.error(f"Error in _parse_response(json_loads):response: {response} error: {error}")
                return None, f"Error in JSON loading the response, error: {error}"

        if "status" not in response or "details" not in response:
            logger.error(f"Missing status/details in response")
            return None, "Missing status/details in response"
        
        status = response["status"]
        details = response["details"]

        if status == "follow-up":
            return json.dumps({"status": status, "details": details}), None


        #details should have a key: domain
        if "domain" not in details:
            logger.error(f"Missing domain in details {response}")
            return None, "Missing domain in details"

        domain = details["domain"]

        if domain not in ["restaurant", "hotel", "attraction", "train", "taxi"]:
            logger.error(f"Invalid domain: {domain}")
            return None, f"Invalid domain: {domain}"
        

        #details should have a key: domain: which is restaurant/hotel/attraction/train/taxi this is different from the literal domain key
        if domain not in details:
            logger.error(f"Missing specific domain: {domain} data in details: {details}")
            use_details = details
        else:
            use_details = details[domain]


        VALIDATION_MODELS = {
            ("restaurant", "db-query"): RestaurantDB,
            ("restaurant", "validate-booking"): RestaurantBook,
            ("hotel", "db-query"): HotelDB,
            ("hotel", "validate-booking"): HotelBook,
            ("attraction", "db-query"): AttractionDB,
            ("attraction", "validate-booking"): AttractionBook,
            ("train", "db-query"): TrainDB,
            ("train", "validate-booking"): TrainBook,
            ("taxi", "db-query"): TaxiDB,
            ("taxi", "validate-booking"): TaxiBook
        }



        if status == "db-query":
            qdata = ["info"]
        else:
            qdata = ["info", "book"]

        logger.info(f"qdata: {qdata}, use_details: {use_details}")
        if any(qd not in use_details for qd in qdata):
            logger.error(f"Missing {qdata} data in the use_details: {use_details}")
            return None, f"Missing {qdata} data in the response: {use_details}"


        result = {}
        for qd in qdata:
            domain_data = use_details.get(qd, {})

            if not domain_data:
                continue

            if qd == "info":
                qd_class = "db-query"
            elif qd == "book":
                qd_class = "validate-booking"
            model_class = VALIDATION_MODELS.get((domain, qd_class))
            logger.info(f"Model class: {model_class}")
            if model_class:
                # Extract only relevant fields from the nested dictionary
                # values are converted to lower in dbquerybuilder.py
                valid_fields = {k.lower(): v for k, v in domain_data.items() if k.lower() in model_class.__annotations__ and v is not None}
                if not valid_fields:
                    logger.error(f"No relevant fields related to {qd_class}:{model_class} are fetched from the model response")
                    return None, f"No relevant fields related to {qd_class}:{model_class} are fetched from the model response"
                result.update(valid_fields)
                logger.info(f"Valid fields: {valid_fields}")
            else:
                return None, f"Model class not found for domain: {domain} and class: {qd_class}"

        if not result:
            logger.error(f"No relevant fields are fetched from the model response: {result}")
            return None, "No relevant fields are fetched from the model response"

        result["domain"] = domain
        return json.dumps({"status": status, "details": result}), None
    

if __name__ == "__main__":
    #test_data = json.dumps({"status": "db-query", "details": {"domain": "train", "destination": "Norwich", "day": "friday"}})
    #test_data = json.dumps({"status": "db-query", "details": {"domain": "train", "info": {"departure": "London Liverpool Street", "destination": "Cambridge", "day": "Tuesday", "leaveAt": {"operator": ">", "value": "13:30"}}}})
    #test_data = json.dumps( {"status": "validate-booking", "details": {"trainID": "TR1395", "people": "8", "departure": "London Liverpool Street", "destination": "Cambridge", "day": "Tuesday", "leaveAt": "13:39", "price": "16.60 pounds"}})
    #test_data = json.dumps({"status": "db-query", "details": {"domain": "train", "info": {"departure": "london", "destination": "cambridge",
    #                                                                                      "day": "tuesday",
    #                                                                                     "leaveat": {"operator": ">=", "value": "13:30"}}}})
    test_data = json.dumps({"status": "validate-booking", "details": {"domain": "restaurant", "info": {"name": "ugly duckling", "phone": "01223244149", "postcode": "cb21tw", "pricerange": "expensive", "area": "centre", "food": "chinese", "people": "3", "day": "saturday", "time": "14:00"}}})
    p = ProcessFuncCallResp()
    print(p.run(test_data))
