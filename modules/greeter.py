# Module to respond to new nodes we haven't seen before with a hello message
# K7MHI Kelly Keeton 2024

import os
import sqlite3
from modules.log import logger
from modules.settings import greeter_db

def initialize_greeter_database():
    try:
        # If the database file doesn't exist, it will be created by sqlite3.connect
        if not os.path.exists(greeter_db):
            logger.info(f"Greeter database file '{greeter_db}' not found. Creating new database.")
        conn = sqlite3.connect(greeter_db)
        c = conn.cursor()
        # Create the table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS greeter
                     (greeter_id INTEGER PRIMARY KEY, greeter_call TEXT, greeter_name TEXT, greeter_qth TEXT, greeter_notes TEXT)''')
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error initializing Greeter database: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def never_seen_before(nodeID):
    # check if we have seen this node before and sent a hello message
    conn = sqlite3.connect(greeter_db)
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM greeter WHERE greeter_call = ?", (nodeID,))
        row = c.fetchone()
        conn.close()
        if row is None:
            # we have not seen this node before
            return True
        else:
            # we have seen this node before
            return False
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            initialize_greeter_database()
            logger.warning("Greeter database table not found, created new table")
            # we have not seen this node before
            return True
        else:
            raise

def hello(nodeID, name):
    # send a hello message
    conn = sqlite3.connect(greeter_db)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO greeter (greeter_call, greeter_name) VALUES (?, ?)", (nodeID, str(name)))
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            initialize_greeter_database()
            c.execute("INSERT INTO greeter (greeter_call, greeter_name) VALUES (?, ?)", (nodeID, str(name)))
        else:
            raise
    conn.commit()
    conn.close()
    return True
