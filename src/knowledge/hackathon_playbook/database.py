"""SQLite database and FTS5 search index for the Hackathon Playbook Knowledge Base."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from config.logging_config import get_logger
from src.knowledge.hackathon_playbook.schema import (
    PlaybookCategory,
    PlaybookEntry,
    PlaybookProvenanceType,
)
from src.knowledge.hackathon_playbook.seed_data import PLAYBOOK_SEED_ENTRIES

logger = get_logger("knowledge.hackathon_playbook.database")

DEFAULT_PLAYBOOK_DB_PATH = Path("data/playbook.db")


class PlaybookDatabase:
    """Manages storage, FTS5 full-text indexing, and search for hackathon playbook entries."""

    def __init__(self, db_path: Path | str = DEFAULT_PLAYBOOK_DB_PATH) -> None:
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.seed_if_empty()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS playbook_entries (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source_origin TEXT NOT NULL,
                    lesson TEXT NOT NULL,
                    actionable_guidance TEXT NOT NULL,
                    target_agent TEXT NOT NULL,
                    kerala_india_applicability TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    provenance_type TEXT NOT NULL DEFAULT 'official_criteria',
                    source_url TEXT NOT NULL DEFAULT '',
                    author_or_creator TEXT NOT NULL DEFAULT '',
                    publication_date TEXT NOT NULL DEFAULT '',
                    transcript_available INTEGER NOT NULL DEFAULT 0,
                    readme_reference TEXT NOT NULL DEFAULT ''
                )
                """
            )
            # Run ALTER TABLE to ensure backward compatibility with older DB schemas
            columns_to_add = [
                ("provenance_type", "TEXT NOT NULL DEFAULT 'official_criteria'"),
                ("source_url", "TEXT NOT NULL DEFAULT ''"),
                ("author_or_creator", "TEXT NOT NULL DEFAULT ''"),
                ("publication_date", "TEXT NOT NULL DEFAULT ''"),
                ("transcript_available", "INTEGER NOT NULL DEFAULT 0"),
                ("readme_reference", "TEXT NOT NULL DEFAULT ''"),
            ]
            for col_name, col_def in columns_to_add:
                try:
                    conn.execute(f"ALTER TABLE playbook_entries ADD COLUMN {col_name} {col_def}")
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # Create FTS5 virtual table
            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS playbook_fts USING fts5(
                        id UNINDEXED,
                        title,
                        lesson,
                        actionable_guidance,
                        kerala_india_applicability,
                        tags,
                        tokenize = 'porter unicode61'
                    )
                    """
                )
            except sqlite3.OperationalError as e:
                logger.warning(f"Could not create FTS5 table, falling back to standard table: {e}")

    def insert_entry(self, entry: PlaybookEntry) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO playbook_entries (
                    id, category, title, source_origin, lesson,
                    actionable_guidance, target_agent, kerala_india_applicability,
                    tags, confidence, provenance_type, source_url,
                    author_or_creator, publication_date, transcript_available,
                    readme_reference
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.category.value if isinstance(entry.category, PlaybookCategory) else str(entry.category),
                    entry.title,
                    entry.source_origin,
                    entry.lesson,
                    entry.actionable_guidance,
                    entry.target_agent,
                    entry.kerala_india_applicability,
                    json.dumps(entry.tags),
                    entry.confidence,
                    entry.provenance_type,
                    entry.source_url,
                    entry.author_or_creator,
                    entry.publication_date,
                    1 if entry.transcript_available else 0,
                    entry.readme_reference,
                ),
            )
            # Update FTS5
            try:
                conn.execute("DELETE FROM playbook_fts WHERE id = ?", (entry.id,))
                conn.execute(
                    """
                    INSERT INTO playbook_fts (
                        id, title, lesson, actionable_guidance,
                        kerala_india_applicability, tags
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
                        entry.title,
                        entry.lesson,
                        entry.actionable_guidance,
                        entry.kerala_india_applicability,
                        " ".join(entry.tags),
                    ),
                )
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def seed_if_empty(self, force: bool = False) -> int:
        """Seed the database with default curated playbook entries if empty or forced."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM playbook_entries")
            count = cur.fetchone()[0]
            if count == 0 or force:
                logger.info(f"Seeding playbook database with {len(PLAYBOOK_SEED_ENTRIES)} entries.")
                for entry in PLAYBOOK_SEED_ENTRIES:
                    self.insert_entry(entry)
                return len(PLAYBOOK_SEED_ENTRIES)
            return count

    def get_by_id(self, entry_id: str) -> PlaybookEntry | None:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM playbook_entries WHERE id = ?", (entry_id,)).fetchone()
            if not row:
                return None
            return self._row_to_entry(row)

    def search(
        self,
        query: str,
        *,
        category: PlaybookCategory | str | None = None,
        target_agent: str | None = None,
        limit: int = 5,
    ) -> list[PlaybookEntry]:
        """Search the playbook using FTS5 with fallback to LIKE query."""
        results: list[PlaybookEntry] = []
        cleaned_words = re.findall(r"[A-Za-z0-9_]{3,}", query)

        with self._get_connection() as conn:
            if cleaned_words:
                fts_query = " OR ".join(f'"{w}"*' for w in cleaned_words[:6])
                try:
                    sql = """
                        SELECT e.* FROM playbook_entries e
                        JOIN playbook_fts f ON e.id = f.id
                        WHERE playbook_fts MATCH ?
                    """
                    params: list[Any] = [fts_query]
                    if category:
                        sql += " AND e.category = ?"
                        params.append(category.value if isinstance(category, PlaybookCategory) else str(category))
                    if target_agent and target_agent != "all":
                        sql += " AND (e.target_agent = ? OR e.target_agent = 'all')"
                        params.append(target_agent)

                    sql += " ORDER BY rank LIMIT ?"
                    params.append(limit)

                    rows = conn.execute(sql, params).fetchall()
                    results = [self._row_to_entry(r) for r in rows]
                except sqlite3.OperationalError as e:
                    logger.debug(f"FTS search failed or not available ({e}), trying fallback.")

            # Fallback if FTS returned nothing or query had no words
            if not results:
                sql = "SELECT * FROM playbook_entries WHERE 1=1"
                params = []
                if category:
                    sql += " AND category = ?"
                    params.append(category.value if isinstance(category, PlaybookCategory) else str(category))
                if target_agent and target_agent != "all":
                    sql += " AND (target_agent = ? OR target_agent = 'all')"
                    params.append(target_agent)
                if cleaned_words:
                    like_clauses = " OR ".join("lesson LIKE ? OR title LIKE ? OR actionable_guidance LIKE ?" for _ in cleaned_words[:3])
                    sql += f" AND ({like_clauses})"
                    for w in cleaned_words[:3]:
                        params.extend([f"%{w}%", f"%{w}%", f"%{w}%"])

                sql += " ORDER BY confidence DESC LIMIT ?"
                params.append(limit)
                rows = conn.execute(sql, params).fetchall()
                results = [self._row_to_entry(r) for r in rows]

        return results

    def list_all(self, limit: int = 100) -> list[PlaybookEntry]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM playbook_entries ORDER BY id LIMIT ?", (limit,)).fetchall()
            return [self._row_to_entry(r) for r in rows]

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> PlaybookEntry:
        tags_raw = row["tags"]
        try:
            tags = json.loads(tags_raw)
        except Exception:
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        # Handle provenance fields gracefully
        keys = row.keys()
        provenance_type = row["provenance_type"] if "provenance_type" in keys and row["provenance_type"] else PlaybookProvenanceType.OFFICIAL_CRITERIA.value
        source_url = row["source_url"] if "source_url" in keys and row["source_url"] else ""
        author_or_creator = row["author_or_creator"] if "author_or_creator" in keys and row["author_or_creator"] else ""
        publication_date = row["publication_date"] if "publication_date" in keys and row["publication_date"] else ""
        transcript_available = bool(row["transcript_available"]) if "transcript_available" in keys else False
        readme_reference = row["readme_reference"] if "readme_reference" in keys and row["readme_reference"] else ""

        return PlaybookEntry(
            id=row["id"],
            category=PlaybookCategory(row["category"]),
            title=row["title"],
            source_origin=row["source_origin"],
            lesson=row["lesson"],
            actionable_guidance=row["actionable_guidance"],
            target_agent=row["target_agent"],
            kerala_india_applicability=row["kerala_india_applicability"],
            tags=tags,
            confidence=float(row["confidence"]),
            provenance_type=provenance_type,
            source_url=source_url,
            author_or_creator=author_or_creator,
            publication_date=publication_date,
            transcript_available=transcript_available,
            readme_reference=readme_reference,
        )
