"""Regression tests for optional official_track_url and schema robustness in HackathonTrack."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.agents.base import is_valid_provenance
from src.database.connection import DatabaseConnection
from src.database.migrations import initialize_database
from src.database.repository import Repository
from src.knowledge.document_intelligence.auto_configurator import (
    HackathonAutoConfigurator,
)
from src.knowledge.document_intelligence.models import (
    DocumentType,
    ExtractedTrack,
    StructuredHackathonDoc,
    UploadedDocument,
)
from src.models.hackathon import HackathonTrack, MultiTrackMode
from src.orchestration.loader import load_multi_track_result


@pytest.fixture()
def test_repo(tmp_path: Path) -> Repository:
    """Isolated SQLite repository for database compatibility tests."""
    db = DatabaseConnection(tmp_path / "track_url_test.db")
    initialize_database(db)
    repo = Repository(db)
    yield repo
    db.close()


def test_1_track_constructed_without_official_track_url() -> None:
    """1. HackathonTrack can be constructed without official_track_url."""
    # Omitted entirely
    t1 = HackathonTrack(name="Agents in Production")
    assert t1.name == "Agents in Production"
    assert t1.official_track_url is None
    assert t1.description is None
    assert t1.track_rules is None

    # Explicit None
    t2 = HackathonTrack(
        name="The Edge",
        description="Edge AI and robotics",
        track_rules="Must run offline",
        official_track_url=None,
    )
    assert t2.official_track_url is None
    assert t2.description == "Edge AI and robotics"

    # Empty string coerced to None
    t3 = HackathonTrack(name="The Rails", official_track_url="   ")
    assert t3.official_track_url is None

    # Construction with 'rules' alias and official_track_url=None
    track = HackathonTrack(
        name="Agents in Production",
        description="Test description",
        rules="Test rules",
        official_track_url=None,
    )
    assert track.name == "Agents in Production"
    assert track.description == "Test description"
    assert track.track_rules == "Test rules"
    assert track.rules == "Test rules"
    assert track.official_track_url is None


def test_2_track_accepts_valid_http_and_https_urls() -> None:
    """2. HackathonTrack accepts official HTTP and HTTPS URLs."""
    t_https = HackathonTrack(
        name="The Trust Layer",
        official_track_url="https://beachhack.in/tracks/trust-layer",
    )
    assert t_https.official_track_url == "https://beachhack.in/tracks/trust-layer"

    t_http = HackathonTrack(
        name="The Toolchain",
        official_track_url="http://beachhack.in/tracks/toolchain",
    )
    assert t_http.official_track_url == "http://beachhack.in/tracks/toolchain"


def test_3_invalid_url_schemes_are_rejected() -> None:
    """3. Invalid URL schemes and private host addresses are rejected."""
    # doc:// internal reference rejected as external track URL
    with pytest.raises(ValidationError, match="Unsupported URL scheme: 'doc'"):
        HackathonTrack(name="The Edge", official_track_url="doc://BeachHack-S08-Tracks.pdf")

    # ftp:// rejected
    with pytest.raises(ValidationError, match="Unsupported URL scheme: 'ftp'"):
        HackathonTrack(name="The Edge", official_track_url="ftp://example.com/edge")

    # javascript: rejected
    with pytest.raises(ValidationError, match="Unsupported URL scheme: 'javascript'"):
        HackathonTrack(name="The Edge", official_track_url="javascript:alert(1)")

    # localhost rejected
    with pytest.raises(ValidationError, match="Blocked host"):
        HackathonTrack(name="The Edge", official_track_url="http://localhost:8080/track")

    # Loopback IP rejected
    with pytest.raises(ValidationError, match="Private or reserved address blocked"):
        HackathonTrack(name="The Edge", official_track_url="http://127.0.0.1:8000/track")


def test_4_all_six_beachhack_tracks_constructed_without_individual_urls() -> None:
    """4. All six BeachHack tracks can be constructed without individual URLs."""
    track_specs = [
        ("Agents in Production", "Software that does the job, and what keeps it in bounds", "In Scope: TOOL USE. Excluded: A chatbot."),
        ("The Toolchain", "Everything you build with, and what it quietly costs", "In Scope: DEVELOPER EXPERIENCE. Excluded: Yet another wrapper."),
        ("The Trust Layer", "Proving a thing is what it claims to be", "In Scope: THREAT DETECTION. Excluded: Simple hashing."),
        ("The Rails", "Rails a billion people already stand on", "In Scope: CREDIT AND FINANCE. Excluded: Crypto speculation."),
        ("The Edge", "Intelligence that runs where the thing actually is", "In Scope: ON-DEVICE MODELS. Excluded: Cloud API proxy."),
        ("Earth Systems", "Water, land, weather, and everything living off them", "In Scope: FISHERIES AND THE SEA. Excluded: Uncalibrated dashboards."),
    ]

    tracks: list[HackathonTrack] = []
    for name, desc, rules in track_specs:
        t = HackathonTrack(
            name=name,
            description=desc,
            track_rules=rules,
            official_track_url=None,
        )
        tracks.append(t)

    assert len(tracks) == 6
    for t in tracks:
        assert t.official_track_url is None
        assert t.name
        assert t.description


def test_5_automatic_hackathon_input_construction_succeeds() -> None:
    """5. Automatic HackathonInput construction succeeds when rulebook has tracks but no URLs."""
    doc = StructuredHackathonDoc(
        hackathon_name="BeachHack Season 08",
        theme="Autonomous Edge & Systems",
        extracted_tracks=[
            ExtractedTrack(name="Agents in Production", description="Agent workflows", track_rules="In Scope: State machines."),
            ExtractedTrack(name="The Edge", description="Edge AI", track_rules="In Scope: Microcontrollers."),
        ],
    )
    uploaded = UploadedDocument(
        id="d-1",
        filename="BeachHack-S08-Tracks.pdf",
        file_type="pdf",
        file_size=2048,
        file_hash="hash_123",
        document_type=DocumentType.OFFICIAL_RULES,
    )

    h_input, status, conflicts = HackathonAutoConfigurator.configure_hackathon(
        profile=doc,
        documents=[uploaded],
    )

    assert h_input is not None
    assert status.is_ready_for_research is True
    assert h_input.is_multi_track is True
    assert len(h_input.tracks) == 2
    for t in h_input.tracks:
        assert t.official_track_url is None
        assert t.description is not None


def test_6_both_multi_track_modes_work() -> None:
    """6. Both multi-track modes work seamlessly."""
    doc = StructuredHackathonDoc(
        hackathon_name="BeachHack Season 08",
        theme="Autonomous Edge & Systems",
        extracted_tracks=[
            ExtractedTrack(name="Track 1", description="D1"),
            ExtractedTrack(name="Track 2", description="D2"),
        ],
    )
    uploaded = UploadedDocument(
        id="d-2",
        filename="BeachHack-S08-Tracks.pdf",
        file_type="pdf",
        file_size=1024,
        file_hash="h2",
    )

    # Mode A
    h_a, _, _ = HackathonAutoConfigurator.configure_hackathon(
        profile=doc,
        documents=[uploaded],
        multi_track_mode=MultiTrackMode.BEST_OVERALL,
    )
    assert h_a is not None
    assert h_a.multi_track_mode == MultiTrackMode.BEST_OVERALL

    # Mode B
    h_b, _, _ = HackathonAutoConfigurator.configure_hackathon(
        profile=doc,
        documents=[uploaded],
        multi_track_mode=MultiTrackMode.BEST_PER_TRACK,
    )
    assert h_b is not None
    assert h_b.multi_track_mode == MultiTrackMode.BEST_PER_TRACK


def test_7_uploaded_document_citations_remain_intact() -> None:
    """7. Uploaded document citations remain intact while external URLs are None."""
    et = ExtractedTrack(
        name="The Edge",
        description="On-device intelligence",
        track_rules="In Scope: Microcontrollers",
        source_filename="BeachHack-S08-Tracks.pdf",
        source_page=12,
        official_track_url=None,
    )
    assert et.citation() == "[Uploaded document: BeachHack-S08-Tracks.pdf, Page 12]"
    assert is_valid_provenance("[Uploaded document: BeachHack-S08-Tracks.pdf, Page 12]", allowed=set()) is True
    assert is_valid_provenance("doc://BeachHack-S08-Tracks.pdf", allowed=set()) is True

    # But doc:// cannot be used as an external track URL
    with pytest.raises(ValidationError):
        HackathonTrack(name="The Edge", official_track_url="doc://BeachHack-S08-Tracks.pdf")


def test_8_existing_historical_database_records_remain_compatible(test_repo: Repository) -> None:
    """8. Existing historical database records (NULL/empty official_url) remain compatible."""
    session_id = test_repo.create_session(
        theme="Legacy Multi-Track Event",
        name="LegacyHack",
        is_multi_track=True,
        multi_track_mode="best_overall",
    )

    # Simulate historical rows with NULL, empty string, and valid URL
    historical_raw_tracks = [
        {"id": "TRK-001", "name": "Legacy Track 1", "description": "Desc 1", "track_rules": "Rules 1", "official_track_url": None},
        {"id": "TRK-002", "name": "Legacy Track 2", "description": "Desc 2", "track_rules": "Rules 2", "official_track_url": ""},
        {"id": "TRK-003", "name": "Legacy Track 3", "description": "Desc 3", "track_rules": "Rules 3", "official_track_url": "https://legacy.org/track3"},
    ]
    test_repo.save_tracks(session_id, historical_raw_tracks)

    # Read rows back directly
    saved_rows = test_repo.get_tracks(session_id)
    assert len(saved_rows) == 3

    # Load via multi-track loader
    loaded_result = load_multi_track_result(session_id, repository=test_repo)
    assert loaded_result is not None
    loaded_tracks = loaded_result.input.tracks
    assert len(loaded_tracks) == 3

    assert loaded_tracks[0].id == "TRK-001"
    assert loaded_tracks[0].official_track_url is None

    assert loaded_tracks[1].id == "TRK-002"
    assert loaded_tracks[1].official_track_url is None

    assert loaded_tracks[2].id == "TRK-003"
    assert loaded_tracks[2].official_track_url == "https://legacy.org/track3"
