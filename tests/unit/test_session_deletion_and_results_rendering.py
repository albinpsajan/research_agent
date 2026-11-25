"""Unit tests for robust session deletion, FK integrity, and results rendering."""

import sqlite3
import uuid
import pytest

from src.database.connection import DatabaseConnection
from src.database.migrations import initialize_database
from src.database.repository import Repository
from src.models.pipeline import (
    PipelineResult,
    ResearchExecutionStatus,
    WinnerOutcome,
)
from src.models.hackathon import HackathonInput


@pytest.fixture
def test_repo(tmp_path):
    db_path = tmp_path / "test_deletion.db"
    db = DatabaseConnection(db_path)
    initialize_database(db)
    return Repository(db)


def test_delete_session_cascades_all_tables_cleanly(test_repo):
    """Verify that deleting a session removes all child records across all 15 tables."""
    sid = str(uuid.uuid4())
    test_repo.create_session(theme="Urban Mobility", name="Mobility Hack", session_id=sid)

    # Insert records across child tables
    with test_repo.db.transaction() as conn:
        pc_id = f"PC-{uuid.uuid4().hex[:6]}"
        conn.execute(
            "INSERT INTO problem_candidates (id, session_id, title, domain) VALUES (?, ?, ?, ?)",
            (pc_id, sid, "Traffic Congestion", "Transportation"),
        )
        cs_id = f"CS-{uuid.uuid4().hex[:6]}"
        conn.execute(
            "INSERT INTO candidate_solutions (id, session_id, problem_candidate_id, problem_statement, proposed_solution) VALUES (?, ?, ?, ?, ?)",
            (cs_id, sid, pc_id, "Heavy traffic during rush hour", "Adaptive traffic lights"),
        )
        conn.execute(
            "INSERT INTO evaluations (session_id, candidate_id, total_score) VALUES (?, ?, ?)",
            (sid, cs_id, 88.5),
        )
        conn.execute(
            "INSERT INTO debate_history (session_id, candidate_id, round_number, criticism) VALUES (?, ?, ?, ?)",
            (sid, cs_id, 1, "High deployment cost"),
        )
        conn.execute(
            "INSERT INTO hackathon_tracks (id, session_id, track_name) VALUES (?, ?, ?)",
            (str(uuid.uuid4()), sid, "Smart Cities"),
        )
        doc_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO uploaded_documents (id, session_id, filename, file_type, file_size, file_hash) VALUES (?, ?, ?, ?, ?, ?)",
            (doc_id, sid, "rules.pdf", "pdf", 1024, "hash123"),
        )
        chunk_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO document_chunks (id, document_id, session_id, page_number, chunk_index, text_content) VALUES (?, ?, ?, ?, ?, ?)",
            (chunk_id, doc_id, sid, 1, 0, "Hackathon guidelines text"),
        )
        conn.execute(
            "INSERT INTO document_chunks_fts (chunk_id, document_id, text_content) VALUES (?, ?, ?)",
            (chunk_id, doc_id, "Hackathon guidelines text"),
        )

    # Execute deletion
    success = test_repo.delete_session(sid)
    assert success is True

    # Verify session and children are gone
    conn = test_repo.db.get_connection()
    assert conn.execute("SELECT count(*) FROM sessions WHERE id = ?", (sid,)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM problem_candidates WHERE session_id = ?", (sid,)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM candidate_solutions WHERE session_id = ?", (sid,)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM evaluations WHERE session_id = ?", (sid,)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM debate_history WHERE session_id = ?", (sid,)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM hackathon_tracks WHERE session_id = ?", (sid,)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM uploaded_documents WHERE session_id = ?", (sid,)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM document_chunks WHERE session_id = ?", (sid,)).fetchone()[0] == 0


def test_delete_session_nonexistent(test_repo):
    """Deleting a non-existent session safely returns False without error."""
    assert test_repo.delete_session("non-existent-session-id") is False


def test_delete_session_with_cross_session_collisions(test_repo):
    """Verify that deleting a session with shared IDs (like P01, C01) never causes a FOREIGN KEY error."""
    s1 = str(uuid.uuid4())
    s2 = str(uuid.uuid4())
    test_repo.create_session(theme="Theme 1", name="Hack 1", session_id=s1)
    test_repo.create_session(theme="Theme 2", name="Hack 2", session_id=s2)

    with test_repo.db.transaction() as conn:
        # Both sessions have problem P01 and candidate C01
        conn.execute(
            "INSERT OR REPLACE INTO problem_candidates (id, session_id, title, domain) VALUES ('P01', ?, 'Prob', 'Dom')",
            (s1,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO candidate_solutions (id, session_id, problem_candidate_id, problem_statement, proposed_solution) VALUES ('C01', ?, 'P01', 'Stmt', 'Sol')",
            (s1,),
        )
        # Session 2 existing_solutions points to P01
        conn.execute(
            "INSERT INTO existing_solutions (session_id, problem_candidate_id, name) VALUES (?, 'P01', 'Existing Sol')",
            (s2,),
        )

    # Deleting s1 must succeed without FOREIGN KEY constraint failed
    assert test_repo.delete_session(s1) is True


def test_pipeline_result_execution_status_and_winner_outcome():
    """Verify execution_status and winner_outcome enum properties on PipelineResult."""
    inp = HackathonInput(theme="AI in Healthcare", name="HealthHack 2026")

    # Interrupted result
    res_interrupted = PipelineResult(
        session_id="test-sess-1",
        input=inp,
        status="interrupted",
    )
    assert res_interrupted.execution_status == ResearchExecutionStatus.INTERRUPTED
    assert res_interrupted.winner_outcome == WinnerOutcome.NOT_EVALUATED

    # Failed result
    res_failed = PipelineResult(
        session_id="test-sess-2",
        input=inp,
        status="failed",
        error="LLM timeout",
    )
    assert res_failed.execution_status == ResearchExecutionStatus.FAILED
    assert res_failed.winner_outcome == WinnerOutcome.NOT_EVALUATED

    # Completed without winner
    res_completed_no_win = PipelineResult(
        session_id="test-sess-3",
        input=inp,
        status="completed_no_winner",
    )
    assert res_completed_no_win.execution_status == ResearchExecutionStatus.COMPLETED
    assert res_completed_no_win.winner_outcome == WinnerOutcome.NO_QUALIFYING_WINNER
