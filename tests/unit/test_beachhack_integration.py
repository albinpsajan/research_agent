"""Integration and acceptance tests for BeachHack Season 08 Document Intelligence and Autonomous Execution."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.database.connection import DatabaseConnection
from src.database.migrations import initialize_database
from src.database.repository import Repository
from src.knowledge.document_intelligence.auto_configurator import (
    HackathonAutoConfigurator,
)
from src.knowledge.document_intelligence.models import (
    DocumentType,
    StructuredHackathonDoc,
    UploadedDocument,
)
from src.knowledge.document_intelligence.service import DocumentIntelligenceService
from src.models.hackathon import MultiTrackMode
from tests.fakes import FakeLLM

BEACHHACK_SAMPLE_FACTS = [
    "BeachHack Season 08 is held from 5th to 7th February 2027.",
    "The event is organized by Christ College of Engineering, Irinjalakuda.",
    "There are six tracks: Agents in Production, The Toolchain, The Trust Layer, The Rails, The Edge, and Earth Systems.",
    "Agents in Production focuses on software that performs tasks autonomously and the machinery around it.",
    "The Toolchain is about tools used by teams to build and deploy software.",
    "The Trust Layer deals with the layer that verifies the authenticity of things like models, software updates, and payments.",
    "The Edge focuses on intelligence that runs where the thing is actually located.",
]

BEACHHACK_RAW_TEXT = """BEACHHACK SEASON 08 5–7 FEBRUARY 2027
SIXTracksTracks
01 Agents in Production Software that does the job, and what keeps it in bounds
02 The Toolchain Everything you build with, and what it quietly costs
03 The Trust Layer Proving a thing is what it claims to be
04 The Rails Rails a billion people already stand on
05 The Edge Intelligence that runs where the thing actually is
06 Earth Systems Water, land, weather, and everything living off them
CODE · CHRIST COLLEGE OF ENGINEERING (AUTONOMOUS), IRINJALAKUDA

TRACK 01 OF 06
AGENTS IN PRODUCTION
Software that does the job, not software that talks about it.
IN SCOPE
TOOL USE PERMISSIONS AND APPROVALS EVALUATION MEMORY AND STATE
NOT THIS TRACK
A chat window wrapped around an API.

TRACK 02 OF 06
THE TOOLCHAIN
The layer every product stands on.
IN SCOPE
DEVELOPER EXPERIENCE BUILD AND DEPLOY OBSERVABILITY DEBUGGING
NOT THIS TRACK
A project management app for developers.

TRACK 03 OF 06
THE TRUST LAYER
Proving a thing is what it claims to be.
IN SCOPE
THREAT DETECTION PROMPT INJECTION DEEPFAKES AND PROVENANCE
NOT THIS TRACK
A password manager with a new interface.

TRACK 04 OF 06
THE RAILS
Rails a billion people already stand on.
IN SCOPE
CREDIT AND FINANCE HEALTH RECORDS LEARNING CIVIC SERVICES
NOT THIS TRACK
Another UPI payment app.

TRACK 05 OF 06
THE EDGE
Intelligence that runs where the thing actually is.
IN SCOPE
ON-DEVICE MODELS ROBOTICS AND DRONES VISION AT THE EDGE
NOT THIS TRACK
A sensor that posts readings to a dashboard.

TRACK 06 OF 06
EARTH SYSTEMS
Water, land, weather, food, and everything living off them.
IN SCOPE
FISHERIES AND THE SEA FLOODS AND LANDSLIDES RIVERS AND GROUNDWATER
NOT THIS TRACK
A dashboard of climate statistics.
"""


@pytest.fixture()
def test_repo(tmp_path: Path) -> Repository:
    """Isolated SQLite repository for integration tests."""
    db = DatabaseConnection(tmp_path / "beachhack_test.db")
    initialize_database(db)
    repo = Repository(db)
    yield repo
    db.close()


def test_enrich_hackathon_profile_extracts_all_six_tracks() -> None:
    """Verifies that enrich_hackathon_profile extracts all 6 tracks with in-scope rules."""
    doc = StructuredHackathonDoc(
        extracted_facts=BEACHHACK_SAMPLE_FACTS,
    )

    enriched = DocumentIntelligenceService.enrich_hackathon_profile(
        doc, BEACHHACK_RAW_TEXT, "BeachHack-S08-Tracks.pdf"
    )

    assert enriched.hackathon_name == "BeachHack Season 08"
    assert "BeachHack Season 08" in enriched.theme
    assert len(enriched.extracted_tracks) == 6
    assert len(enriched.tracks) == 6

    expected_names = [
        "Agents in Production",
        "The Toolchain",
        "The Trust Layer",
        "The Rails",
        "The Edge",
        "Earth Systems",
    ]
    for idx, expected in enumerate(expected_names):
        track = enriched.extracted_tracks[idx]
        assert track.name == expected
        assert len(track.description) > 5
        assert "In Scope:" in track.track_rules
        assert "Excluded:" in track.track_rules


def test_auto_configurator_deadline_and_multi_track_structure() -> None:
    """Verifies that HackathonAutoConfigurator produces a valid HackathonInput from enriched doc."""
    doc = StructuredHackathonDoc(
        extracted_facts=BEACHHACK_SAMPLE_FACTS,
    )
    enriched = DocumentIntelligenceService.enrich_hackathon_profile(
        doc, BEACHHACK_RAW_TEXT, "BeachHack-S08-Tracks.pdf"
    )

    uploaded_doc = UploadedDocument(
        id="doc-123",
        filename="BeachHack-S08-Tracks.pdf",
        file_type="pdf",
        file_size=1024,
        file_hash="abc123hash",
        document_type=DocumentType.OFFICIAL_RULES,
    )

    h_input, status, conflicts = HackathonAutoConfigurator.configure_hackathon(
        profile=enriched,
        documents=[uploaded_doc],
        multi_track_mode=MultiTrackMode.BEST_OVERALL,
    )

    assert h_input is not None
    assert status.is_ready_for_research is True
    assert status.missing_essential == []
    assert h_input.name == "BeachHack Season 08"
    assert "BeachHack Season 08" in h_input.theme
    assert h_input.deadline is not None
    assert h_input.deadline.year == 2027
    assert h_input.deadline.month == 2
    assert h_input.deadline.day == 7
    assert h_input.is_multi_track is True
    assert h_input.multi_track_mode == MultiTrackMode.BEST_OVERALL
    assert len(h_input.tracks) == 6

    # Verify Mode B works equally cleanly
    h_input_b, status_b, _ = HackathonAutoConfigurator.configure_hackathon(
        profile=enriched,
        documents=[uploaded_doc],
        multi_track_mode=MultiTrackMode.BEST_PER_TRACK,
    )
    assert h_input_b is not None
    assert h_input_b.multi_track_mode == MultiTrackMode.BEST_PER_TRACK


def test_get_active_auto_configuration_integration(test_repo: Repository, tmp_path: Path) -> None:
    """Verifies that DocumentIntelligenceService retrieves active auto-configuration from repository."""
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    service = DocumentIntelligenceService(repository=test_repo, llm=FakeLLM(), uploads_dir=uploads_dir)

    # Initially empty
    assert service.get_active_auto_configuration() is None

    # Insert document and chunks
    doc_id = "test-beachhack-doc"
    test_repo.save_uploaded_document(
        doc_id=doc_id,
        filename="BeachHack-S08-Tracks.pdf",
        file_type="pdf",
        file_size=1024,
        file_hash="unique_hash_1",
        document_type=DocumentType.OFFICIAL_RULES.value,
        page_count=1,
        extraction_method="embedded_text",
        status="extracted",
    )
    test_repo.save_document_chunks([
        {
            "id": "chunk-1",
            "document_id": doc_id,
            "page_number": 1,
            "chunk_index": 0,
            "content_type": "text",
            "text_content": BEACHHACK_RAW_TEXT,
            "extraction_method": "embedded_text",
            "confidence": 1.0,
        }
    ])

    raw_doc = StructuredHackathonDoc(
        extracted_facts=BEACHHACK_SAMPLE_FACTS,
    )
    test_repo.save_document_structured_extraction(
        doc_id=doc_id,
        extraction_type="hackathon_profile",
        data_json=raw_doc.model_dump_json(),
    )

    # Now get_active_auto_configuration should auto-enrich and return complete HackathonInput
    h_input = service.get_active_auto_configuration()
    assert h_input is not None
    assert h_input.name == "BeachHack Season 08"
    assert h_input.is_multi_track is True
    assert len(h_input.tracks) == 6
    assert h_input.tracks[0].name == "Agents in Production"
    assert h_input.tracks[1].name == "The Toolchain"
    assert h_input.tracks[2].name == "The Trust Layer"
    assert h_input.tracks[3].name == "The Rails"
    assert h_input.tracks[4].name == "The Edge"
    assert h_input.tracks[5].name == "Earth Systems"
