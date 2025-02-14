import sqlite3

import clemgame
from clemgame import get_logger

logger = get_logger(__name__)


class DBRetriever:
    def __init__(self, domains, dbpath):
        logger.error(f"DBRetriever: domain:{domains} dbpath:{dbpath}")
        self.domains = domains
        self.dbpath = dbpath
        self.dbcon = {}
        self._prepare_db_connection(domains)

    def _prepare_db_connection(self, domains):
        for domain in domains:
            self.dbcon[domain] = sqlite3.connect(f"{self.dbpath}/{domain}-dbase.db")

    def getcolumns(self, domains=None):

        dbcolumns = {}

        if domains is None:
            domains = self.domains

        for domain in domains:
            connection = self.dbcon.get(domain)
            if connection is None:
                logger.error(f"Domain {domain} not found in dbcon.")
                continue
            
            dbcolumns[domain] = []
            cursor = connection.cursor()
            cursor.execute(f"PRAGMA table_info({domain})")
            column_names = [row[1] for row in cursor.fetchall()]
            dbcolumns[domain] = column_names

            # Close the connection
            cursor.close()

        return dbcolumns


    def run(self, domain, query, values):

        if domain not in self.domains:
            logger.error(f"Domain {domain} not found in domains.")
            return []
        
        dbcon = self.dbcon[domain]
        dbcon.row_factory = sqlite3.Row
        cursor = dbcon.cursor()

        try:
            cursor.execute(query, values)
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
            return result if len(result) <= 5 else result[:5]
        finally:
            # Cleanup
            cursor.close()
            #self.dbcon.close()
        
    
    def reset(self, domain):
        if domain is None:
            for domain in self.domains:
                self.dbcon[domain].close()
        else:
            self.dbcon[domain].close()

