"""Versioned database migrations for HackathonIQ.

Migrations are append-only.  Never edit an applied migration: add a new one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.logging_config import get_logger
from src.database.connection import DatabaseConnection

logger = get_logger("migrations")

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    sql: str


MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "Initial schema", SCHEMA_PATH.read_text(encoding="utf-8")),
    Migration(
        2,
        "Uniqueness and intelligence indexes",
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_intelligence_url
            ON intelligence_items(url) WHERE url IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_research_source_session_url
            ON research_sources(session_id, url);
        CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at);
        CREATE INDEX IF NOT EXISTS idx_agent_results_session_agent
            ON agent_results(session_id, agent_name);
        CREATE INDEX IF NOT EXISTS idx_debate_session_candidate
            ON debate_history(session_id, candidate_id, round_number);
        """,
    ),
    Migration(
        3,
        "Multi-track hackathon support and cross-track comparisons",
        """
        CREATE TABLE IF NOT EXISTS hackathon_tracks (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            track_name TEXT NOT NULL,
            description TEXT,
            track_rules TEXT,
            official_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS multi_track_comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            mode TEXT NOT NULL,
            winning_track_id TEXT,
            winning_candidate_id TEXT,
            comparison_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_tracks_session ON hackathon_tracks(session_id);
        CREATE INDEX IF NOT EXISTS idx_multi_track_comparisons_session ON multi_track_comparisons(session_id);
        ALTER TABLE sessions ADD COLUMN is_multi_track INTEGER DEFAULT 0;
        ALTER TABLE sessions ADD COLUMN multi_track_mode TEXT DEFAULT 'best_overall';
        """,
    ),
    Migration(
        4,
        "Document intelligence, uploaded files, page chunks, FTS5 index and structured extraction",
        """
        CREATE TABLE IF NOT EXISTS uploaded_documents (
            id TEXT PRIMARY KEY,
            session_id TEXT REFERENCES sessions(id),
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_hash TEXT NOT NULL,
            document_type TEXT NOT NULL DEFAULT 'general_evidence',
            page_count INTEGER DEFAULT 1,
            extraction_method TEXT NOT NULL DEFAULT 'embedded_text',
            status TEXT NOT NULL DEFAULT 'uploaded',
            warnings_json TEXT DEFAULT '[]',
            metadata_json TEXT DEFAULT '{}',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS document_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES uploaded_documents(id) ON DELETE CASCADE,
            session_id TEXT REFERENCES sessions(id),
            page_number INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'text',
            text_content TEXT NOT NULL,
            tables_json TEXT DEFAULT '[]',
            extraction_method TEXT NOT NULL DEFAULT 'embedded_text',
            confidence REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS document_structured_extractions (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL UNIQUE REFERENCES uploaded_documents(id) ON DELETE CASCADE,
            session_id TEXT REFERENCES sessions(id),
            extraction_type TEXT NOT NULL DEFAULT 'hackathon_profile',
            data_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_uploaded_docs_session ON uploaded_documents(session_id);
        CREATE INDEX IF NOT EXISTS idx_uploaded_docs_hash ON uploaded_documents(file_hash);
        CREATE INDEX IF NOT EXISTS idx_doc_chunks_doc ON document_chunks(document_id);
        CREATE INDEX IF NOT EXISTS idx_doc_chunks_session ON document_chunks(session_id);
        CREATE INDEX IF NOT EXISTS idx_doc_chunks_page ON document_chunks(document_id, page_number);

        CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(
            chunk_id UNINDEXED,
            document_id UNINDEXED,
            text_content,
            tokenize = 'porter unicode61'
        );
        """,
    ),
    Migration(
        5,
        "Performance optimization indexes",
        """
        CREATE INDEX IF NOT EXISTS idx_uploaded_docs_active_session
            ON uploaded_documents(is_active, session_id);
        CREATE INDEX IF NOT EXISTS idx_evaluations_session_score
            ON evaluations(session_id, total_score DESC);
        CREATE INDEX IF NOT EXISTS idx_sessions_status
            ON sessions(status);
        CREATE INDEX IF NOT EXISTS idx_problem_candidates_session
            ON problem_candidates(session_id);
        CREATE INDEX IF NOT EXISTS idx_candidate_solutions_session
            ON candidate_solutions(session_id);
        """,
    ),
    Migration(
        6,
        "Candidate solution backfill for historical integrity",
        """
        INSERT OR IGNORE INTO candidate_solutions (id, session_id, problem_statement, proposed_solution)
        SELECT DISTINCT candidate_id, session_id, 'Historical problem statement', 'Historical candidate solution'
        FROM evaluations
        WHERE candidate_id IS NOT NULL AND candidate_id NOT IN (SELECT id FROM candidate_solutions);

        INSERT OR IGNORE INTO candidate_solutions (id, session_id, problem_statement, proposed_solution)
        SELECT DISTINCT candidate_id, session_id, 'Historical problem statement', 'Historical candidate solution'
        FROM debate_history
        WHERE candidate_id IS NOT NULL AND candidate_id NOT IN (SELECT id FROM candidate_solutions);
        """,
    ),
)


def get_current_version(db: DatabaseConnection) -> int:
    """Get the current schema version (0 if the database is new)."""
    try:
        exists = db.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'"
        )
        if not exists:
            return 0
        row = db.fetch_one("SELECT MAX(version) AS v FROM migrations")
        return int(row["v"]) if row and row["v"] is not None else 0
    except Exception:  # noqa: BLE001 - a missing table means version 0
        return 0


def run_migrations(db: DatabaseConnection) -> None:
    """Apply every pending migration in order."""
    current = get_current_version(db)
    for migration in MIGRATIONS:
        if migration.version <= current:
            continue
        logger.info(
            "Applying migration %03d: %s", migration.version, migration.description
        )
        with db.transaction() as conn:
            conn.executescript(migration.sql)
            conn.execute(
                "INSERT INTO migrations (version, description) VALUES (?, ?)",
                (migration.version, migration.description),
            )
        logger.info("Migration %03d applied", migration.version)
    logger.info("Database at version %s", get_current_version(db))


def initialize_database(db: DatabaseConnection) -> None:
    """Initialize the database with all migrations."""
    logger.info("Initializing database at %s", db.db_path)
    run_migrations(db)
    logger.info("Database initialization complete")
