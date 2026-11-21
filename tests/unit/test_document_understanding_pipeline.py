"""Tests for Intelligent Document Understanding, Auto-Configuration, and Autonomous Research Execution."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.database.connection import DatabaseConnection
from src.database.migrations import initialize_database
from src.database.repository import Repository
from src.knowledge.document_intelligence.auto_configurator import (
    HackathonAutoConfigurator,
)
from src.knowledge.document_intelligence.classifier import DocumentClassifier
from src.knowledge.document_intelligence.consolidator import DocumentConsolidator
from src.knowledge.document_intelligence.models import (
    DocumentType,
    ExtractedTrack,
    StructuredHackathonDoc,
    UploadedDocument,
)
from src.knowledge.document_intelligence.service import DocumentIntelligenceService
from src.models.hackathon import MultiTrackMode
from tests.fakes import FakeLLM


def _make_pdf_bytes(page_texts: list[str]) -> bytes:
    """Generate a valid, multi-page PDF with selectable embedded text streams."""
    pages_count = len(page_texts)
    kids_refs = " ".join(f"{3 + i * 3} 0 R" for i in range(pages_count))
    parts: list[bytes] = [b"%PDF-1.4\n", b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"]
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


@pytest.fixture
def test_db(tmp_path: Path) -> Repository:
    db_path = tmp_path / "test_doc_pipeline.db"
    conn = DatabaseConnection(str(db_path))
    initialize_database(conn)
    return Repository(conn)


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def doc_service(test_db: Repository, fake_llm: FakeLLM, tmp_path: Path) -> DocumentIntelligenceService:
    uploads = tmp_path / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    return DocumentIntelligenceService(
        repository=test_db,
        llm=fake_llm,
        uploads_dir=uploads,
    )


# ---------------------------------------------------------------------------
# 1. Document Classification Tests
# ---------------------------------------------------------------------------


def test_document_classification_heuristics() -> None:
    classifier = DocumentClassifier()

    # Rulebook
    t_rules, c_rules = classifier.classify_document(
        "KCC_2026_Guidelines.pdf",
        "Official Rules and Hackathon Guidelines. Evaluation criteria, judging rubric, submission deadline.",
    )
    assert t_rules == DocumentType.OFFICIAL_RULES
    assert c_rules >= 0.90

    # Track Brief
    t_track, c_track = classifier.classify_document(
        "Agriculture_Tracks.pdf",
        "Hackathon Challenge Areas and Track Descriptions. Tracks: Smart Canopy Sensing.",
    )
    assert t_track == DocumentType.TRACK_DESCRIPTION
    assert c_track >= 0.85

    # Research Paper
    t_paper, c_paper = classifier.classify_document(
        "canopy_microclimate.pdf",
        "Abstract: This study examines agro-ecological canopy density in Kerala polders. Methodology and experimental results. References:\n[1] Smith et al.",
    )
    assert t_paper == DocumentType.RESEARCH_PAPER
    assert c_paper >= 0.90

    # Government Report
    t_gov, c_gov = classifier.classify_document(
        "ksdma_flood_survey.pdf",
        "Government of Kerala, Department of Disaster Management. Annual survey report on Kuttanad flooding.",
    )
    assert t_gov == DocumentType.GOVERNMENT_REPORT
    assert c_gov >= 0.85


# ---------------------------------------------------------------------------
# 2. Structured Provenance Grounding Tests
# ---------------------------------------------------------------------------


def test_structured_hackathon_doc_provenance(doc_service: DocumentIntelligenceService) -> None:
    text = (
        "Kerala Civic Challenge 2026 Official Rulebook.\n"
        "Organizer: Kerala State Planning Board.\n"
        "Theme: Resilient Coastal Infrastructure.\n"
        "Track 1: Estuarine Water Management.\n"
        "Track 2: Decentralized Healthcare.\n"
        "Technical Restrictions: Must avoid mandatory paid APIs. Offline first.\n"
        "Judging Criteria: 30% Feasibility, 30% Local Relevance, 20% Innovation, 20% Demo Polish.\n"
        "Submission Deadline: 2026-11-30.\n"
    )
    pdf_bytes = _make_pdf_bytes([text])

    doc = doc_service.upload_document(
        filename="kcc_rules.pdf",
        file_bytes=pdf_bytes,
        document_type=DocumentType.OFFICIAL_RULES,
        extract_structured=True,
    )

    struct = doc_service.repository.get_document_structured_extraction(doc.id)
    assert struct is not None
    assert struct["data"] is not None

    p = StructuredHackathonDoc.model_validate(struct["data"])
    assert p.hackathon_name is not None
    # Check provenance
    prov_name = p.get_field_provenance("hackathon_name")
    assert prov_name is not None
    assert prov_name.filename == "kcc_rules.pdf"
    assert "[Uploaded document: kcc_rules.pdf, Page 1]" in prov_name.citation()

    assert len(p.extracted_tracks) >= 1 or len(p.tracks) >= 1


# ---------------------------------------------------------------------------
# 3. Multi-Document Consolidation & Conflict Detection
# ---------------------------------------------------------------------------


def test_multi_document_consolidation_and_conflict_detection() -> None:
    # Doc A: Official Guidelines with deadline Oct 15
    prof_a = StructuredHackathonDoc(
        hackathon_name="Smart Kerala Hackathon 2026",
        organizer="Digital University Kerala",
        theme="Sustainable Agro-Tech",
        submission_deadline="2026-10-15",
        event_duration="36 hours",
        tracks=["Agro-Tech Canopy Sensing"],
        technical_restrictions=["No paid proprietary APIs"],
    )

    # Doc B: Announcement Flyer with different deadline Nov 01 and extra track
    prof_b = StructuredHackathonDoc(
        hackathon_name="Smart Kerala Hackathon 2026",
        submission_deadline="2026-11-01",
        tracks=["Rural Primary Health Triage"],
        technical_restrictions=["Open-source licenses only"],
    )

    profiles = [
        (prof_a, "Doc_A_Guidelines.pdf", DocumentType.OFFICIAL_RULES),
        (prof_b, "Doc_B_Flyer.pdf", DocumentType.EVENT_ANNOUNCEMENT),
    ]

    consolidated, conflicts = DocumentConsolidator.consolidate_hackathon_profiles(profiles)

    # Verify official rules priority for deadline
    assert consolidated.submission_deadline == "2026-10-15"
    assert consolidated.organizer == "Digital University Kerala"

    # Verify tracks merged across documents
    track_names = [t.name for t in consolidated.extracted_tracks]
    assert "Agro-Tech Canopy Sensing" in track_names
    assert "Rural Primary Health Triage" in track_names
    assert len(track_names) == 2

    # Verify conflict detected and flagged
    assert len(conflicts) >= 1
    dl_conflict = next((c for c in conflicts if c.field == "submission_deadline"), None)
    assert dl_conflict is not None
    assert "Doc_A_Guidelines.pdf" in dl_conflict.source_a
    assert "Doc_B_Flyer.pdf" in dl_conflict.source_b
    assert "2026-10-15" in dl_conflict.item_a
    assert "2026-11-01" in dl_conflict.item_b


# ---------------------------------------------------------------------------
# 4. Auto-Configuration Engine Tests
# ---------------------------------------------------------------------------


def test_auto_configuration_multi_track() -> None:
    profile = StructuredHackathonDoc(
        hackathon_name="Kerala Smart Innovation Challenge",
        theme="Civic Resilience and Climate Adaptation",
        organizer="KSDMA & Dept of Agriculture",
        submission_deadline="2026-12-01",
        event_duration="48 hours",
        extracted_tracks=[
            ExtractedTrack(name="Flood Micro-Catchments", description="Polder inundation prediction"),
            ExtractedTrack(name="Agro-Ecological Sensing", description="Smallholder crop canopy monitoring"),
        ],
        technical_restrictions=["Must run on local hardware", "No paid cloud services"],
    )

    mock_docs = [
        UploadedDocument(
            id="doc-1",
            filename="ksic_rules.pdf",
            file_type="pdf",
            file_size=1024,
            file_hash="hash1",
            document_type=DocumentType.OFFICIAL_RULES,
        )
    ]

    h_input, status, _conflicts = HackathonAutoConfigurator.configure_hackathon(
        profile=profile,
        documents=mock_docs,
        multi_track_mode=MultiTrackMode.BEST_OVERALL,
    )

    assert status.is_ready_for_research is True
    assert h_input is not None
    assert h_input.name == "Kerala Smart Innovation Challenge"
    assert h_input.theme == "Civic Resilience and Climate Adaptation"
    assert h_input.is_multi_track is True
    assert len(h_input.tracks) == 2
    assert h_input.tracks[0].name == "Flood Micro-Catchments"
    assert h_input.tracks[1].name == "Agro-Ecological Sensing"
    assert h_input.deadline is not None
    assert h_input.deadline.strftime("%Y-%m-%d") == "2026-12-01"
    assert "Event Duration: 48 hours" in h_input.constraints
    assert "No paid cloud services" in h_input.constraints


def test_auto_configuration_missing_deadline_not_fabricated() -> None:
    # Rulebook with no deadline specified
    profile = StructuredHackathonDoc(
        hackathon_name="Civic Open Ideathon",
        theme="Open Data for Urban Transit",
        tracks=["Public Bus Dispatch"],
    )

    mock_docs = [
        UploadedDocument(
            id="doc-1",
            filename="ideathon.pdf",
            file_type="pdf",
            file_size=1024,
            file_hash="hash1",
            document_type=DocumentType.OFFICIAL_RULES,
        )
    ]

    h_input, status, _ = HackathonAutoConfigurator.configure_hackathon(
        profile=profile,
        documents=mock_docs,
    )

    assert status.is_ready_for_research is True
    assert h_input is not None
    # Deadline must remain None and not fabricated!
    assert h_input.deadline is None


def test_auto_configuration_missing_theme_stops_cleanly() -> None:
    # Empty profile with no theme and no tracks
    profile = StructuredHackathonDoc(
        hackathon_name=None,
        theme=None,
        tracks=[],
    )

    h_input, status, _ = HackathonAutoConfigurator.configure_hackathon(
        profile=profile,
        documents=[],
    )

    assert status.is_ready_for_research is False
    assert "theme" in status.missing_essential
    assert h_input is None


# ---------------------------------------------------------------------------
# 5. Non-Hackathon Research Paper Routing
# ---------------------------------------------------------------------------


def test_non_hackathon_research_paper_routing() -> None:
    paper_profile = StructuredHackathonDoc(
        problem_statements=["Saline intrusion in Kuttanad paddy fields causes 40% yield drop."],
        technical_restrictions=["Low-cost sensor deployment required"],
    )

    mock_docs = [
        UploadedDocument(
            id="paper-1",
            filename="saline_intrusion_study.pdf",
            file_type="pdf",
            file_size=2048,
            file_hash="paperhash",
            document_type=DocumentType.RESEARCH_PAPER,
        )
    ]

    h_input, status, _ = HackathonAutoConfigurator.configure_hackathon(
        profile=paper_profile,
        documents=mock_docs,
    )

    assert status.is_ready_for_research is True
    assert h_input is not None
    # Configures evidence-driven problem discovery session
    assert "Saline intrusion in Kuttanad" in h_input.theme
    assert h_input.is_multi_track is False


# ---------------------------------------------------------------------------
# 6. End-to-End Autonomous Research Execution
# ---------------------------------------------------------------------------


def test_execute_automated_research_end_to_end(doc_service: DocumentIntelligenceService) -> None:
    # Ingest mock rulebook
    rulebook_text = (
        "Kerala State Civic Challenge 2026.\n"
        "Theme: Agro-Ecological Resilience for Kuttanad Smallholders.\n"
        "Organizer: Dept of Agriculture, Kerala.\n"
        "Technical Rules: No mandatory paid APIs. Offline first.\n"
        "Judging Criteria: Technical Feasibility 30%, Regional Relevance 30%, Originality 20%, Demo 20%.\n"
    )
    pdf_bytes = _make_pdf_bytes([rulebook_text])

    doc_service.upload_document(
        filename="kerala_agro_challenge.pdf",
        file_bytes=pdf_bytes,
        document_type=DocumentType.OFFICIAL_RULES,
        extract_structured=True,
    )

    # Auto-configure hackathon
    h_input, status, _conflicts, _profile = doc_service.auto_configure_hackathon()
    assert status.is_ready_for_research is True
    assert h_input is not None
    assert "Resilient Coastal Infrastructure" in h_input.theme

    # Execute automated research
    progress_calls: list[tuple[str, str, float]] = []

    def mock_progress(stage: str, msg: str, frac: float) -> None:
        progress_calls.append((stage, msg, frac))

    result = doc_service.execute_automated_research(
        hackathon_input=h_input,
        progress_callback=mock_progress,
    )

    assert result is not None
    assert result.session_id is not None
    assert len(progress_calls) >= 1

    # Verify report was generated and contains primary document provenance
    report = getattr(result, 'master_report', None) or getattr(result, 'report', None)
    assert report is not None
    markdown = report.markdown if hasattr(report, "markdown") else str(report)
    assert "kerala_agro_challenge.pdf" in markdown
    assert "Uploaded Primary Documents & Provenance Citations" in markdown
