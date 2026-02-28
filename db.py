import logging
import sqlite3
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)

DB_FILE = "mod_versions.db"


class DatabaseError(Exception):
    """Raised when a database operation fails."""
    pass


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connections that ensures proper cleanup."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.OperationalError as e:
        logger.error(f"Database operational error: {e}")
        raise DatabaseError(f"Failed to connect to database: {e}") from e
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        raise DatabaseError(f"Database error: {e}") from e
    finally:
        if conn is not None:
            conn.close()


def init_db() -> tuple[sqlite3.Connection, sqlite3.Cursor]:
    """
    Initializes the SQLite database and returns a connection and cursor.
    Creates the mod_versions table if it does not exist.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mod_versions (
                project_id TEXT PRIMARY KEY,
                version_number TEXT,
                file_url TEXT,
                file_size INTEGER,
                sha1 TEXT,
                sha512 TEXT,
                mod_loader TEXT
            )
        """)
        conn.commit()
        logger.info("Database initialized successfully.")
        return conn, cursor
    except sqlite3.OperationalError as e:
        logger.error(f"Failed to create database table: {e}")
        raise DatabaseError(f"Failed to initialize database: {e}") from e
    except sqlite3.Error as e:
        logger.error(f"Database initialization failed: {e}")
        raise DatabaseError(f"Database initialization failed: {e}") from e


def get_mod_version(project_id: str) -> sqlite3.Row | None:
    """Retrieve a mod version by project ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM mod_versions WHERE project_id = ?", (project_id,))
        return cursor.fetchone()


def save_mod_version(
    project_id: str,
    version_number: str,
    file_url: str,
    file_size: int,
    sha1: str,
    sha512: str,
    mod_loader: str,
) -> None:
    """Save or update a mod version in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO mod_versions (project_id, version_number, file_url, file_size, sha1, sha512, mod_loader)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                version_number = excluded.version_number,
                file_url = excluded.file_url,
                file_size = excluded.file_size,
                sha1 = excluded.sha1,
                sha512 = excluded.sha512,
                mod_loader = excluded.mod_loader
        """, (project_id, version_number, file_url, file_size, sha1, sha512, mod_loader))
        conn.commit()
