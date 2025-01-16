import copy
import json
from fuzzywuzzy import process

import clemgame
from games.dmsystem_monolithic_llm.dbretriever import DBRetriever

logger = clemgame.get_logger(__name__)


class SchemaManager:
    """
    Manages the external database schema.
    """

    def __init__(self, schema, domain, dbcolumns, thresholdvalue):
        # Load schema (assume it is passed as a dictionary)
        self.domain = domain
        self.dbcolumns = dbcolumns
        self.thresholdvalue = thresholdvalue
        self.schema = {}
        self._saveschema(schema)



    def _formatslots(self, service_name, slotsdict):
        updatedslots = {}
        for slot in slotsdict:
            name = slot['name'].split(f"{service_name}-")[1].strip()
            updatedslots[name] = slot
        return updatedslots


    def _saveschema(self, schema):
        self.schema = schema

        defaultslots = self.schema[self.domain]["slots"]
        updatedslots = {}
        for slot in defaultslots:
            updatedslots[slot['name']] = slot

        self.schema[self.domain]["slots"] = updatedslots

    def get_columns(self, domain):
        """Return all column names for the table."""
        #Table columns and schema columns are not matching - hence returning Table columns
        return self.dbcolumns#self.schema[domain]["slots"].keys()

    def get_valid_values(self, domain, column):
        """Return valid values for a column, if available."""
        return self.schema[domain]["slots"].get(column, {}).get("possible_values", None)

    def map_user_field(self, domain, user_field):
        """Map user fields to database column names using fuzzy matching."""
        columns = self.get_columns(domain)
        logger.info(f"SchemaManager: Domain: {domain} DBColumns: {columns}")
        #logger.info(f"SchemaManager: Columns: {columns}")
        match, score = process.extractOne(user_field, columns)
        logger.info(f"SchemaManager: query column: {user_field} match: {match} score: {score} self.thresholdvalue: {self.thresholdvalue}")
        return match if score >= self.thresholdvalue else None
    
    def map_user_value(self, domain, column, user_value):
        """Map user values to valid values for a column, if available."""
        valid_values = self.get_valid_values(domain, column)
        if valid_values:
            match, score = process.extractOne(user_value, valid_values)
            return match if score >= self.thresholdvalue else None
        return None


class DBQueryBuilder:
    def __init__(self, domain, dbpath, schema, catslots, noncatslots, thresholdvalue, errormsgs):
        self.domain = domain
        self.dbpath = dbpath
        self.schema = schema
        self.catslots = catslots
        self.noncatslots = noncatslots
        self.errormsgs = errormsgs
        self.table_name = f"{domain}"

        self.dbretriever = DBRetriever(domain, dbpath)
        dbcolumns = self.dbretriever.getcolumns()
        #Get the intersection of catslots and dbcolumns
        self.dbcolumns = list(set(catslots).intersection(set(dbcolumns)))
        self.schema_manager = SchemaManager(schema, domain, self.dbcolumns, thresholdvalue)

    def _setto_lower(self, slots: dict) -> dict:
        return {
            str(key).lower(): str(value).lower()
            for key, value in slots.items()
        }

    def _process_query(self, slotsdict):
        """
        Process user query to generate a normalized representation.
        user_query: dictionary with extracted user fields and values.
        """
        ftslotsdict = self._setto_lower(slotsdict)
        normalized_query = {}
        for user_field, user_value in ftslotsdict.items():
            # Map user field to database column
            column = self.schema_manager.map_user_field(self.domain, user_field)
            if not column:
                continue

            #if column not in self.catslots:
            #    continue

            #TODO: Normalize values
            if isinstance(user_value, list):
                normalized_query[column] = ", ".join(user_value)
            else:
                normalize_value = self.schema_manager.map_user_value(self.domain, column, user_value)
                normalized_query[column] = normalize_value if normalize_value else user_value

        return normalized_query

    def run(self, slotsdict):
        dwhere = self._process_query(slotsdict)
        logger.info(f"DB Query dwhere: {dwhere}")
        if not dwhere:
            return {"status": "failure", "data": None, "error": self.errormsgs["nocolumnmatch"]}

        where_clause = " AND ".join([f"{key} = ?" for key in dwhere.keys()])
        values = tuple(dwhere.values())
        query = f"SELECT * FROM {self.domain} WHERE {where_clause};"
        logger.info(f"DB Query: {query} Values: {values} Domain {self.domain}")
        try:
            domaindata = self.dbretriever.run(query, values)

            if not domaindata:
                poss_values = {}
                column_keys = list(dwhere.keys())
                for clmn in column_keys:
                    poss_values[clmn] = self.schema_manager.get_valid_values(self.domain, clmn)

                errormsg = self.errormsgs["novaluematch"].replace("$values", json.dumps(poss_values))

                return {"status": "failure", "data": None, "error": errormsg}
            return {"status": "success", "data": domaindata, "error": None}
        except Exception as error:
            logger.error(f"Error in DB Query: {error}")
            return {"status": "failure", "data": None, "error": str(error)}

    def get_valid_values(self, slot_name):
        return self.schema_manager.get_valid_values(self.domain, slot_name)
    
    def getcolumns(self):
        return self.dbcolumns

    def reset(self):
        self.dbretriever.reset()


if __name__ == "__main__":

    def _normalize_domain_schema(domain, domain_schema):
        normalized_schema = {}
        for entry in domain_schema:
            if entry["service_name"] != domain:
                continue
            normalized_entry = copy.deepcopy(entry)
            normalized_entry["slots"] = [
                {
                    "name": slot["name"].split("-")[1].strip(),
                    "is_categorical": slot["is_categorical"],
                    "possible_values": slot["possible_values"] if "possible_values" in slot else [],
                }
                for slot in entry["slots"]
            ]
            normalized_schema[entry["service_name"]] = normalized_entry
        return normalized_schema


    with open("/home/admin/Desktop/codebase/cocobots/clembenchfork_dm_code/clembench/games/dmsystem_monolithic_llm/resources/domains/en/schema.json", "r") as f:
        domainschema = json.load(f)
    
    domainschema = _normalize_domain_schema("restaurant", domainschema)

    cat_slots = ["pricerange", "area", "bookday", "bookpeople"]
    noncat_slots = [
              "food",
              "name",
              "booktime",
              "address",
              "phone",
              "postcode",
              "ref"
            ]
    dbq = DBQueryBuilder("restaurant", "games/dmsystem_monolithic_llm/resources/domains/en/restaurant-dbase.db",
                         domainschema, cat_slots, noncat_slots, 70, None)
    
    #qslots = {'location': 'centre of town', 'date': 'Friday', 'time': '14:15', 'party_size': 4, 'cuisine': 'Chinese'}
    #result = dbq.run(qslots)
    #print(result)
    print(dbq.get_valid_values("area"))