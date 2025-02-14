import copy
import json
from fuzzywuzzy import process

import clemgame
from games.todsystem.dbretriever import DBRetriever

logger = clemgame.get_logger(__name__)


class SchemaManager:
    """
    Manages the external database schema.
    """

    def __init__(self, schema, domains, dbcolumns):
        # Load schema (assume it is passed as a dictionary)
        self.domains = domains
        self.dbcolumns = dbcolumns
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

        for domain in self.domains:
            defaultslots = self.schema[domain]["slots"]
            updatedslots = {}
            for slot in defaultslots:
                updatedslots[slot['name']] = slot

            self.schema[domain]["slots"] = updatedslots

    def get_columns(self, domain):
        """Return all column names for the table."""
        #Table columns and schema columns are not matching - hence returning Table columns
        return self.dbcolumns[domain]#self.schema[domain]["slots"].keys()

    def get_valid_values(self, domain, column):
        """Return valid values for a column, if available."""
        return self.schema[domain]["slots"].get(column, {}).get("possible_values", None)


class DBQueryBuilder:
    def __init__(self, domains, schema, dbpath, errormsgs):
        self.domains = domains
        self.dbpath = dbpath
        self.errormsgs = errormsgs

        self.dbretriever = DBRetriever(self.domains, dbpath)
        self.dbcolumns = self.dbretriever.getcolumns(self.domains)
        self.schema_manager = SchemaManager(schema, domains, self.dbcolumns)

    def _setto_lower(self, slots: dict) -> dict:
        return {
            str(key).lower(): str(value).lower()
            for key, value in slots.items()
        }

    def run(self, slotsdict):
        logger.info(f"DB Query run: {slotsdict}")
        domain = slotsdict.get("domain", None)
        if domain is None:
            return {"status": "failure", "data": None, "error": self.errormsgs["nodomainmatch"]}

        dwhere = {k.lower():str(v).lower() for k, v in slotsdict.items() if k != "domain" and v and not isinstance(v, (list, dict, tuple))}

        logger.info(f"DB Query dwhere: {dwhere} {type(dwhere)}")
        if not dwhere:
            return {"status": "failure", "data": None, "error": self.errormsgs["nocolumnmatch"]}

        #dwhere = {key: value for key, value in dwhere.items() if value}

        where_clause = " AND ".join([f"{key} = ?" for key in dwhere.keys()])
        values = tuple(dwhere.values())
        query = f"SELECT * FROM {domain} WHERE {where_clause};"
        logger.info(f"DB Query: {query} Values: {values} Domain {domain}")
        try:
            domaindata = self.dbretriever.run(domain, query, values)

            if not domaindata:
                poss_values = {}
                column_keys = list(dwhere.keys())
                for clmn in column_keys:
                    poss_values[clmn] = self.schema_manager.get_valid_values(domain, clmn)

                errormsg = self.errormsgs["novaluematch"]#.replace("$values", json.dumps(poss_values))

                return {"status": "failure", "data": None, "error": errormsg}
            return {"status": "success", "data": domaindata, "error": None}
        except Exception as error:
            logger.error(f"Error in DB Query: {error}")
            return {"status": "failure", "data": None, "error": str(error)}


    def get_valid_values(self, domain, slot_name):
        return self.schema_manager.get_valid_values(domain, slot_name)
    
    def getcolumns(self, domain):
        return self.dbcolumns.get(domain, [])

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

    dbq = DBQueryBuilder("restaurant", domainschema,
                         "games/dmsystem_monolithic_llm/resources/domains/en/restaurant-dbase.db", None)
    
    #qslots = {'location': 'centre of town', 'date': 'Friday', 'time': '14:15', 'party_size': 4, 'cuisine': 'Chinese'}
    #result = dbq.run(qslots)
    #print(result)
    print(dbq.getcolumns())