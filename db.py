import sqlite3
import logging

DB_FILE = "mod_versions.db"

def init_db():
    """
    Initializes the SQLite database and returns a connection and cursor.
    Creates the mod_versions table if it does not exist.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mod_versions (
                project_id TEXT PRIMARY KEY,
                version_number TEXT,
                file_url TEXT,
                file_size INTEGER,
                sha1 TEXT,
                sha512 TEXT,
                mod_loader TEXT
            )
        ''')
        conn.commit()
        logging.info("Database initialized successfully.")
        return conn, cursor
    except Exception as e:
        logging.error(f"Database initialization failed: {e}")
        raise
