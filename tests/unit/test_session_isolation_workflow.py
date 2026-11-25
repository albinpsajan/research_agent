"""Unit and workflow tests for research session isolation, form reset, and background execution.

Verifies the 15-step multi-session isolation scenario:
1. Ingest BeachHack document in Session A.
2. Verify BeachHack auto-extraction.
3. Start research for Session A.
4. Verify New Research state reset (zero contamination).
5. Ingest CleanTech document in Session B.
6. Verify CleanTech auto-extraction with zero BeachHack leakage.
7. Start research for Session B.
8. Verify both sessions exist independently with isolated tracks, documents, and results.
9. Verify background runner lifecycle and non-blocking execution.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.database.connection import DatabaseConnection
from src.database.migrations import initialize_database
from src.database.repository import Repository
from src.knowledge.document_intelligence.models import (
    DocumentType,
    ExtractedTrack,
    ExtractionMethod,
    ExtractionStatus,
    StructuredHackathonDoc,
    UploadedDocument,
)
from src.knowledge.document_intelligence.service import DocumentIntelligenceService
from src.models.hackathon import HackathonInput, HackathonTrack, MultiTrackMode
from src.models.pipeline import PipelineOptions
from src.orchestration.background_runner import (
    get_job_status,
    is_job_active,
    start_research_job,
)
from tests.fakes import FakeLLM


def _make_pdf_bytes(page_texts: list[str]) -> bytes:
    """Generate a valid, multi-page PDF with selectable embedded text streams."""
    pages_count = len(page_texts)
    kids_refs = " ".join(f"{3 + i * 3} 0 R" for i in range(pages_count))
    parts: list[bytes] = []
    parts.append(b"%PDF-1.4\n")
    parts.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    parts.append(f"2 0 obj << /Type /Pages /Kids [{kids_refs}] /Count {pages_count} >> endobj\n".encode("ascii"))
    obj_id = 3
    for text in page_texts:
        page_obj_id = obj_id
        font_obj_id = obj_id + 1
        stream_obj_id = obj_id + 2
        obj_id += 3
        safe_text = text.replace("(", "\\(").replace(")", "\\)")
        stream_content = f"BT /F1 12 Tf 72 712 Td ({safe_text}) Tj ET\n".encode()
        stream_len = len(stream_content)
        parts.append(f"{page_obj_id} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_obj_id} 0 R >> >> /Contents {stream_obj_id} 0 R >> endobj\n".encode("ascii"))
        parts.append(f"{font_obj_id} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n".encode("ascii"))
        parts.append(f"{stream_obj_id} 0 obj << /Length {stream_len} >> stream\n".encode("ascii") + stream_content + b"endstream\nendobj\n")
    parts.append(f"trailer << /Root 1 0 R /Size {obj_id} >>\nstartxref\n0\n%%EOF\n".encode("ascii"))
    return b"".join(parts)


@pytest.fixture()
def test_repo(tmp_path: Path) -> Repository:
    """Isolated SQLite repository for integration tests."""
    db = DatabaseConnection(tmp_path / "session_isolation_test.db")
    initialize_database(db)
    repo = Repository(db)
    yield repo
    db.close()


def test_15_step_session_isolation_and_workflow(test_repo: Repository, tmp_path: Path) -> None:
    """Execute the mandatory 15-step session isolation verification scenario."""
    fake_llm = FakeLLM()
    service = DocumentIntelligenceService(repository=test_repo, llm=fake_llm)

    session_a_id = f"sess_a_{uuid.uuid4().hex[:8]}"
    session_b_id = f"sess_b_{uuid.uuid4().hex[:8]}"

    # -------------------------------------------------------------------------
    # Step 1: Initialize Session A
    # -------------------------------------------------------------------------
    assert test_repo.list_uploaded_documents(session_id=session_a_id) == []

    # -------------------------------------------------------------------------
    # Step 2: Upload BeachHack Document for Session A
    # -------------------------------------------------------------------------
    beachhack_pdf_content = _make_pdf_bytes(["BeachHack Season 08 Guidelines and Rules. 6 tracks."])
    doc_a = service.upload_document(
        filename="BeachHack_Season_08.pdf",
        file_bytes=beachhack_pdf_content,
        document_type=DocumentType.OFFICIAL_RULES,
        session_id=session_a_id,
        extract_structured=False,
    )
    assert doc_a.session_id == session_a_id

    # Seed structured extraction for BeachHack into Session A
    bh_struct = StructuredHackathonDoc(
        hackathon_name="BeachHack Season 08",
        theme="Sustainable Coastal Engineering: AI & Maritime Systems",
        tracks=["Agents in Production", "The Toolchain", "The Trust Layer"],
        extracted_tracks=[
            ExtractedTrack(name="Agents in Production", description="Autonomous software agents.", track_rules="Tool use and memory"),
            ExtractedTrack(name="The Toolchain", description="Developer infrastructure and CI/CD.", track_rules="Build and deploy"),
            ExtractedTrack(name="The Trust Layer", description="Security and provenance.", track_rules="Threat detection"),
        ],
    )
    test_repo.save_document_structured_extraction(
        doc_id=doc_a.id,
        extraction_type="hackathon_profile",
        data_json=bh_struct.model_dump_json(),
        session_id=session_a_id,
    )

    # -------------------------------------------------------------------------
    # Step 3: Verify BeachHack Auto-Extraction for Session A
    # -------------------------------------------------------------------------
    cfg_a = service.get_active_auto_configuration(session_id=session_a_id)
    assert cfg_a is not None
    assert cfg_a.name == "BeachHack Season 08"
    assert "BeachHack Season 08" in cfg_a.theme or "Sustainable Coastal" in cfg_a.theme
    assert len(cfg_a.tracks) == 3
    assert {t.name for t in cfg_a.tracks} == {"Agents in Production", "The Toolchain", "The Trust Layer"}

    # -------------------------------------------------------------------------
    # Step 4: Start Research on Session A -> Persist Session A in Repository
    # -------------------------------------------------------------------------
    test_repo.create_session(
        theme=cfg_a.theme,
        name=cfg_a.name,
        session_id=session_a_id,
        is_multi_track=True,
        multi_track_mode="best_overall",
    )
    test_repo.save_tracks(session_a_id, cfg_a.tracks)
    test_repo.attach_documents_to_session(session_a_id, [doc_a.id])

    sess_a_record = test_repo.get_session(session_a_id)
    assert sess_a_record is not None
    assert sess_a_record["hackathon_name"] == "BeachHack Season 08"
    tracks_a = test_repo.get_tracks(session_a_id)
    assert len(tracks_a) == 3

    # -------------------------------------------------------------------------
    # Step 5: Simulate Form Reset (Switching to New Research for Session B)
    # -------------------------------------------------------------------------
    # In New Research, get_active_auto_configuration is queried with session_b_id
    cfg_b_pre = service.get_active_auto_configuration(session_id=session_b_id)
    # MUST BE NONE! Zero BeachHack leakage into fresh session B
    assert cfg_b_pre is None

    # -------------------------------------------------------------------------
    # Step 6: Verify Session A's Documents & Tracks are Isolated to Session A
    # -------------------------------------------------------------------------
    docs_for_a = test_repo.list_uploaded_documents(session_id=session_a_id)
    docs_for_b = test_repo.list_uploaded_documents(session_id=session_b_id)
    assert len(docs_for_a) == 1
    assert docs_for_a[0]["filename"] == "BeachHack_Season_08.pdf"
    assert len(docs_for_b) == 0

    # -------------------------------------------------------------------------
    # Step 7: Open Session B and Confirm Form Fields are Completely Empty
    # -------------------------------------------------------------------------
    default_theme_b = cfg_b_pre.theme if cfg_b_pre else ""
    default_name_b = cfg_b_pre.name if cfg_b_pre else ""
    default_tracks_b = cfg_b_pre.tracks if cfg_b_pre else []
    assert default_theme_b == ""
    assert default_name_b == ""
    assert default_tracks_b == []

    # -------------------------------------------------------------------------
    # Step 8: Upload Distinct Hackathon Document in Session B (CleanTech 2027)
    # -------------------------------------------------------------------------
    cleantech_pdf_content = _make_pdf_bytes(["CleanTech Global 2027 Guidelines and Rules. Carbon capture."])
    doc_b = service.upload_document(
        filename="CleanTech_Global_2027.pdf",
        file_bytes=cleantech_pdf_content,
        document_type=DocumentType.OFFICIAL_RULES,
        session_id=session_b_id,
        extract_structured=False,
    )
    assert doc_b.id != doc_a.id

    # Seed structured extraction for CleanTech into Session B
    ct_struct = StructuredHackathonDoc(
        hackathon_name="CleanTech Global 2027",
        theme="Zero Emissions: Carbon Capture & Grid Optimization",
        tracks=["Carbon Sequestration", "Smart Grid AI"],
        extracted_tracks=[
            ExtractedTrack(name="Carbon Sequestration", description="Direct air capture technologies.", track_rules="Measurable carbon offset"),
            ExtractedTrack(name="Smart Grid AI", description="Decentralized solar routing.", track_rules="Sub-second latency"),
        ],
    )
    test_repo.save_document_structured_extraction(
        doc_id=doc_b.id,
        extraction_type="hackathon_profile",
        data_json=ct_struct.model_dump_json(),
        session_id=session_b_id,
    )

    # -------------------------------------------------------------------------
    # Step 9: Verify CleanTech Extraction Populates Session B Strictly
    # -------------------------------------------------------------------------
    cfg_b = service.get_active_auto_configuration(session_id=session_b_id)
    assert cfg_b is not None
    assert cfg_b.name == "CleanTech Global 2027"
    assert "CleanTech Global 2027" in cfg_b.theme or "Zero Emissions" in cfg_b.theme
    assert len(cfg_b.tracks) == 2
    assert {t.name for t in cfg_b.tracks} == {"Carbon Sequestration", "Smart Grid AI"}

    # -------------------------------------------------------------------------
    # Step 10: Confirm Zero BeachHack Contamination in Session B
    # -------------------------------------------------------------------------
    for t in cfg_b.tracks:
        assert "Beach" not in t.name
        assert "Toolchain" not in t.name
        assert "Trust Layer" not in t.name
    assert "BeachHack" not in cfg_b.theme
    assert "BeachHack" not in (cfg_b.name or "")

    # -------------------------------------------------------------------------
    # Step 11: Start Research on Session B
    # -------------------------------------------------------------------------
    test_repo.create_session(
        theme=cfg_b.theme,
        name=cfg_b.name,
        session_id=session_b_id,
        is_multi_track=True,
        multi_track_mode="best_overall",
    )
    test_repo.save_tracks(session_b_id, cfg_b.tracks)
    test_repo.attach_documents_to_session(session_b_id, [doc_b.id])

    sess_b_record = test_repo.get_session(session_b_id)
    assert sess_b_record is not None
    assert sess_b_record["hackathon_name"] == "CleanTech Global 2027"

    # -------------------------------------------------------------------------
    # Step 12: Verify Session B Tracks and Documents Belong Strictly to Session B
    # -------------------------------------------------------------------------
    tracks_b = test_repo.get_tracks(session_b_id)
    assert len(tracks_b) == 2
    assert {t["track_name"] for t in tracks_b} == {"Carbon Sequestration", "Smart Grid AI"}

    docs_b_final = test_repo.list_uploaded_documents(session_id=session_b_id)
    assert len(docs_b_final) == 1
    assert docs_b_final[0]["filename"] == "CleanTech_Global_2027.pdf"

    # -------------------------------------------------------------------------
    # Step 13: Load Session A and Verify Integrity (Zero CleanTech Leaked to A)
    # -------------------------------------------------------------------------
    loaded_a = test_repo.get_session(session_a_id)
    assert loaded_a["hackathon_name"] == "BeachHack Season 08"
    loaded_tracks_a = test_repo.get_tracks(session_a_id)
    assert len(loaded_tracks_a) == 3
    assert {t["track_name"] for t in loaded_tracks_a} == {"Agents in Production", "The Toolchain", "The Trust Layer"}
    for t in loaded_tracks_a:
        assert "Carbon" not in t["track_name"]
        assert "Smart Grid" not in t["track_name"]

    # -------------------------------------------------------------------------
    # Step 14: Load Session B and Verify Integrity (Zero BeachHack Leaked to B)
    # -------------------------------------------------------------------------
    loaded_b = test_repo.get_session(session_b_id)
    assert loaded_b["hackathon_name"] == "CleanTech Global 2027"
    loaded_tracks_b = test_repo.get_tracks(session_b_id)
    assert len(loaded_tracks_b) == 2
    assert {t["track_name"] for t in loaded_tracks_b} == {"Carbon Sequestration", "Smart Grid AI"}

    # -------------------------------------------------------------------------
    # Step 15: Verify Deleting Session A Leaves Session B 100% Intact
    # -------------------------------------------------------------------------
    test_repo.delete_session(session_a_id)
    assert test_repo.get_session(session_a_id) is None
    assert test_repo.get_tracks(session_a_id) == []

    # Session B is completely unaffected
    remaining_b = test_repo.get_session(session_b_id)
    assert remaining_b is not None
    assert remaining_b["hackathon_name"] == "CleanTech Global 2027"
    assert len(test_repo.get_tracks(session_b_id)) == 2
    assert len(test_repo.list_uploaded_documents(session_id=session_b_id)) == 1


def test_cross_session_document_cloning(test_repo: Repository) -> None:
    """Verifies that uploading the same PDF in two sessions creates independent records."""
    service = DocumentIntelligenceService(repository=test_repo, llm=FakeLLM())

    sess_1 = f"s1_{uuid.uuid4().hex[:6]}"
    sess_2 = f"s2_{uuid.uuid4().hex[:6]}"

    same_content = _make_pdf_bytes(["Shared hackathon rulebook across seasons."])

    # Upload in session 1
    doc1 = service.upload_document(
        filename="Rulebook.pdf",
        file_bytes=same_content,
        document_type=DocumentType.OFFICIAL_RULES,
        session_id=sess_1,
        extract_structured=False,
    )

    # Seed structured extraction for session 1
    struct1 = StructuredHackathonDoc(hackathon_name="Season 1", theme="Theme 1")
    test_repo.save_document_structured_extraction(
        doc_id=doc1.id,
        extraction_type="hackathon_profile",
        data_json=struct1.model_dump_json(),
        session_id=sess_1,
    )

    # Upload same file in session 2
    doc2 = service.upload_document(
        filename="Rulebook.pdf",
        file_bytes=same_content,
        document_type=DocumentType.OFFICIAL_RULES,
        session_id=sess_2,
        extract_structured=False,
    )

    # Both sessions have their own records in SQLite
    docs_s1 = test_repo.list_uploaded_documents(session_id=sess_1)
    docs_s2 = test_repo.list_uploaded_documents(session_id=sess_2)

    assert len(docs_s1) == 1
    assert len(docs_s2) == 1
    assert docs_s1[0]["id"] == doc1.id
    assert docs_s2[0]["id"] == doc2.id
    assert doc1.id != doc2.id  # Unique doc IDs per session

    # Structured extraction was cloned to session 2
    s2_struct = test_repo.get_document_structured_extraction(doc2.id)
    assert s2_struct is not None
    assert s2_struct["session_id"] == sess_2


def test_background_runner_lifecycle(test_repo: Repository) -> None:
    """Verifies background job launch, non-blocking thread execution, and status polling."""
    session_id = f"job_sess_{uuid.uuid4().hex[:8]}"

    hackathon = HackathonInput(
        theme="Decentralized Energy Grids",
        name="EnergyHack",
        is_multi_track=False,
    )
    options = PipelineOptions()

    # Pre-create session in repository
    test_repo.create_session(
        theme=hackathon.theme,
        name=hackathon.name,
        session_id=session_id,
    )

    # Initial status query before launch
    status_pre = get_job_status(session_id, repository=test_repo)
    assert status_pre is not None
    assert status_pre["status"] == "created"
    assert is_job_active(session_id) is False

    # Launch background job with mock worker
    from unittest.mock import patch

    with patch("src.orchestration.background_runner._research_worker") as mock_worker:
        # Prevent actual thread from calling Ollama
        launched = start_research_job(session_id, hackathon, options)
        assert launched is True

        # Check job is in-memory and running
        assert is_job_active(session_id) is True
        status_running = get_job_status(session_id, repository=test_repo)
        assert status_running["status"] == "running"
        assert status_running["theme"] == "Decentralized Energy Grids"
        assert status_running["progress"] > 0.0

        # Cannot re-launch while running
        re_launched = start_research_job(session_id, hackathon, options)
        assert re_launched is False


def test_delete_session_with_shared_candidate_ids(test_repo: Repository) -> None:
    """Verifies that delete_session handles cross-session shared candidate IDs without IntegrityError."""
    s1 = f"s1_{uuid.uuid4().hex[:6]}"
    s2 = f"s2_{uuid.uuid4().hex[:6]}"

    test_repo.create_session(theme="Theme 1", session_id=s1)
    test_repo.create_session(theme="Theme 2", session_id=s2)

    # Save problem and candidate with shared ID 'C01'
    with test_repo.db.transaction() as conn:
        conn.execute("INSERT INTO problem_candidates (id, session_id, title, domain) VALUES ('P01', ?, 'Prob 1', 'Dom 1')", (s1,))
        conn.execute("INSERT INTO candidate_solutions (id, session_id, problem_candidate_id, proposed_solution) VALUES ('C01', ?, 'P01', 'Sol 1')", (s1,))
        conn.execute("INSERT INTO evaluations (session_id, candidate_id, total_score) VALUES (?, 'C01', 8.5)", (s2,))

    # Deleting s1 must succeed cleanly without FOREIGN KEY constraint failed error
    deleted = test_repo.delete_session(s1)
    assert deleted is True
    assert test_repo.get_session(s1) is None
    # s2 still exists
    assert test_repo.get_session(s2) is not None
