import sqlite3

import clemgame
from clemgame import get_logger

logger = get_logger(__name__)


class DBRetriever:
    def __init__(self, domain, dbpath):
        logger.error(f"DBRetriever: domain:{domain} dbpath:{dbpath}")
        self.domain = domain
        self.dbcon = sqlite3.connect(dbpath)

    def getcolumns(self):
        cursor = self.dbcon.cursor()
        cursor.execute(f"PRAGMA table_info({self.domain})")
        column_names = [row[1] for row in cursor.fetchall()]

        # Close the connection
        cursor.close()

        return column_names


    def run(self, query, values):
        self.dbcon.row_factory = sqlite3.Row
        cursor = self.dbcon.cursor()

        try:
            cursor.execute(query, values)
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
            return result
        finally:
            # Cleanup
            cursor.close()
            #self.dbcon.close()
        
    
    def reset(self):
        self.dbcon.close()
