"""SQLite database connection management.

Streamlit executes reruns on different threads, so the cached connection is
opened with ``check_same_thread=False`` and every operation is serialized with
a re-entrant lock.  WAL mode still allows other processes to read.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from config.logging_config import get_logger
from config.settings import get_settings

logger = get_logger("database")


class DatabaseConnection:
    """Thread-safe manager for one SQLite database connection."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path or get_settings().db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    def get_connection(self) -> sqlite3.Connection:
        """Get or create the shared database connection."""
        with self._lock:
            if self._connection is None:
                self._connection = sqlite3.connect(
                    str(self.db_path),
                    # Access is serialized by self._lock below. Streamlit may
                    # call from different script-runner threads.
                    check_same_thread=False,
                    # Timestamps are stored as ISO-8601 text and parsed by the
                    # Pydantic models; SQLite's TIMESTAMP converter cannot
                    # parse the "T" separator.
                    detect_types=0,
                )
                self._connection.row_factory = sqlite3.Row
                self._connection.execute("PRAGMA journal_mode=WAL")
                self._connection.execute("PRAGMA foreign_keys=ON")
                self._connection.execute("PRAGMA busy_timeout=5000")
                logger.info("Database connected: %s", self.db_path)
            return self._connection

    @contextmanager
    def transaction(self):
        """Serialize a multi-statement transaction."""
        with self._lock:
            conn = self.get_connection()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a SQL statement under the connection lock."""
        with self._lock:
            conn = self.get_connection()
            try:
                return conn.execute(sql, params)
            except sqlite3.Error as exc:
                logger.error("SQL error: %s | SQL: %s", exc, sql[:200])
                raise

    def execute_many(self, sql: str, params_list: list[tuple]) -> None:
        """Execute a SQL statement with multiple parameter sets."""
        with self._lock:
            conn = self.get_connection()
            try:
                conn.executemany(sql, params_list)
                conn.commit()
            except sqlite3.Error as exc:
                conn.rollback()
                logger.error("SQL error in executemany: %s", exc)
                raise

    def fetch_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        """Fetch a single row while holding the lock."""
        with self._lock:
            cursor = self.execute(sql, params)
            return cursor.fetchone()

    def fetch_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Fetch all rows while holding the lock."""
        with self._lock:
            cursor = self.execute(sql, params)
            return cursor.fetchall()

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._connection:
                self._connection.close()
                self._connection = None
                logger.info("Database connection closed")


_db: DatabaseConnection | None = None
_db_lock = threading.Lock()


def get_db(db_path: Path | None = None) -> DatabaseConnection:
    """Get or create the global database connection."""
    global _db
    with _db_lock:
        if _db is None:
            _db = DatabaseConnection(db_path)
        return _db


def reset_db() -> None:
    """Reset the database connection (for testing)."""
    global _db
    with _db_lock:
        if _db:
            _db.close()
        _db = None
