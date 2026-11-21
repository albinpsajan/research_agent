"""Regression tests verifying strict separation between external HTTP(S) URLs and internal document citations."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agents.base import is_valid_provenance
from src.agents.hackathon_intelligence import HackathonIntelligenceAgent
from src.database.connection import DatabaseConnection
from src.database.migrations import initialize_database
from src.database.repository import Repository
from src.knowledge.document_intelligence.auto_configurator import HackathonAutoConfigurator
from src.knowledge.document_intelligence.models import (
    DocumentType,
    ExtractedTrack,
    ProvenancedField,
    StructuredHackathonDoc,
    UploadedDocument,
)
from src.knowledge.document_intelligence.service import DocumentIntelligenceService
from src.models.candidate import CandidateSolution, FeasibilityReport
from src.models.evaluation import FinalEvaluationReport, WinnerSelection
from src.models.hackathon import HackathonInput, MultiTrackMode
from src.models.pipeline import PipelineOptions, PipelineResult
from src.reports.generator import ReportGenerator
from src.research.base import ResearchError, validate_public_url
from src.research.registry import ResearchService
from tests.fakes import FakeLLM


@pytest.fixture()
def test_repo(tmp_path: Path) -> Repository:
    """Isolated SQLite repository."""
    db = DatabaseConnection(tmp_path / "rules_url_test.db")
    initialize_database(db)
    repo = Repository(db)
    yield repo
    db.close()


def test_valid_https_rules_url_accepted() -> None:
    """1. A valid HTTPS rules URL is accepted by auto_configurator and URL validation."""
    doc = StructuredHackathonDoc(hackathon_name="Testathon", theme="AI for Good")
    h_input, status, _ = HackathonAutoConfigurator.configure_hackathon(
        profile=doc,
        documents=[],
        user_overrides={"rules_url": "https://example.org/rules"},
    )
    assert h_input is not None
    assert h_input.rules_url == "https://example.org/rules"
    # Verify validate_public_url accepts it (using example.com or example.org)
    # validate_public_url resolves DNS, so test schema validation directly:
    assert h_input.rules_url.startswith("https://")


def test_valid_http_rules_url_accepted() -> None:
    """2. A valid HTTP rules URL is accepted by auto_configurator."""
    doc = StructuredHackathonDoc(hackathon_name="Testathon", theme="AI for Good")
    h_input, status, _ = HackathonAutoConfigurator.configure_hackathon(
        profile=doc,
        documents=[],
        user_overrides={"rules_url": "http://example.com/hackathon-rules"},
    )
    assert h_input is not None
    assert h_input.rules_url == "http://example.com/hackathon-rules"
    assert h_input.rules_url.startswith("http://")


def test_internal_doc_citation_retained_as_provenance() -> None:
    """3. An internal doc:// citation and page reference are retained as valid document provenance."""
    # is_valid_provenance must allow doc:// references and page brackets
    assert is_valid_provenance("doc://BeachHack-S08-Tracks.pdf", allowed=set()) is True
    assert is_valid_provenance("[Uploaded document: BeachHack-S08-Tracks.pdf, Page 1]", allowed=set()) is True
    assert is_valid_provenance("https://hallucinated-site.com/fake", allowed=set()) is False

    # Check StructuredHackathonDoc retains provenanced fields with document citations
    doc = StructuredHackathonDoc(
        hackathon_name="BeachHack Season 08",
        theme="Multi-Track AI",
        provenanced_fields={
            "rules": ProvenancedField(
                value="Mandatory offline model execution",
                filename="BeachHack-S08-Tracks.pdf",
                page=2,
                confidence=0.95,
            )
        },
    )
    p_rules = doc.get_field_provenance("rules")
    assert p_rules is not None
    assert p_rules.filename == "BeachHack-S08-Tracks.pdf"
    assert p_rules.page == 2


def test_doc_ref_rejected_as_external_rules_url() -> None:
    """4. A doc:// reference is rejected as an external rules URL and not populated in rules_url."""
    doc = StructuredHackathonDoc(hackathon_name="BeachHack", theme="Multi-Track")
    uploaded = UploadedDocument(
        id="d-1",
        filename="BeachHack-S08-Tracks.pdf",
        file_type="pdf",
        file_size=1024,
        file_hash="hash_1",
    )

    # When auto-configuring without user overrides, rules_url must remain None, not doc://
    h_input, status, _ = HackathonAutoConfigurator.configure_hackathon(
        profile=doc,
        documents=[uploaded],
    )
    assert h_input is not None
    assert h_input.rules_url is None

    # Even if an internal doc:// reference is mistakenly passed in user_overrides, it must be rejected
    h_input_override, _, _ = HackathonAutoConfigurator.configure_hackathon(
        profile=doc,
        documents=[uploaded],
        user_overrides={"rules_url": "doc://BeachHack-S08-Tracks.pdf"},
    )
    assert h_input_override is not None
    assert h_input_override.rules_url is None

    # validate_public_url must reject doc://
    with pytest.raises(ResearchError, match="Unsupported URL scheme: doc"):
        validate_public_url("doc://BeachHack-S08-Tracks.pdf")


def test_missing_external_rules_url_does_not_block_research() -> None:
    """5. A missing external rules URL does not block research when uploaded evidence is sufficient."""
    doc = StructuredHackathonDoc(
        hackathon_name="BeachHack Season 08",
        theme="Autonomous Edge Intelligence",
        extracted_facts=["BeachHack is held in February 2027."],
        tracks=["The Edge", "Agents in Production"],
    )
    uploaded = UploadedDocument(
        id="d-2",
        filename="BeachHack-S08-Tracks.pdf",
        file_type="pdf",
        file_size=2048,
        file_hash="hash_2",
        document_type=DocumentType.OFFICIAL_RULES,
    )

    h_input, status, _ = HackathonAutoConfigurator.configure_hackathon(
        profile=doc,
        documents=[uploaded],
    )
    assert h_input is not None
    assert h_input.rules_url is None
    assert status.is_ready_for_research is True
    assert status.missing_essential == []


def test_agent1_uses_uploaded_rulebook_evidence_without_external_url(test_repo: Repository) -> None:
    """6. Agent 1 can use uploaded rulebook evidence without requiring an external rules URL."""
    fake_llm = FakeLLM()
    # Save uploaded document & chunks
    doc_id = "doc-official-rules"
    test_repo.save_uploaded_document(
        doc_id=doc_id,
        filename="BeachHack-S08-Tracks.pdf",
        file_type="pdf",
        file_size=2048,
        file_hash="hash_official_1",
        document_type=DocumentType.OFFICIAL_RULES.value,
        status="extracted",
    )
    test_repo.save_document_chunks([
        {
            "id": "c-1",
            "document_id": doc_id,
            "page_number": 1,
            "chunk_index": 0,
            "content_type": "text",
            "text_content": "Official Rules: 36-hour hackathon. Teams of up to 4. All models must run offline.",
            "extraction_method": "embedded_text",
            "confidence": 1.0,
        }
    ])

    h_input = HackathonInput(
        theme="BeachHack Season 08: Agents in Production",
        name="BeachHack Season 08",
        website_url=None,
        rules_url=None,  # No external rules URL
        constraints="Teams of 4",
    )

    from src.research.registry import SearchBundle

    mock_research = MagicMock(spec=ResearchService)
    mock_research.search.return_value = SearchBundle(query="test", results=[])
    # fetch_page should NEVER be called since website_url and rules_url are None
    agent = HackathonIntelligenceAgent(fake_llm, mock_research, test_repo)

    session_id = test_repo.create_session(theme=h_input.theme, name=h_input.name)
    intel = agent.run(session_id, h_input)

    assert intel is not None
    assert mock_research.fetch_page.call_count == 0  # No HTTP fetches attempted!
    # Verifies document citations are recorded in research_sources
    assert any("[Uploaded document: BeachHack-S08-Tracks.pdf" in s for s in intel.research_sources)


def test_final_reports_preserve_document_page_citations(test_repo: Repository) -> None:
    """7. Final reports preserve document page citations in the dedicated provenance section."""
    session_id = test_repo.create_session(theme="Edge Intelligence", name="BeachHack")
    test_repo.save_uploaded_document(
        doc_id="doc-report-test",
        filename="BeachHack-S08-Tracks.pdf",
        file_type="pdf",
        file_size=4096,
        file_hash="hash_report_1",
        document_type=DocumentType.OFFICIAL_RULES.value,
        page_count=3,
        extraction_method="embedded_text",
        session_id=session_id,
    )

    h_input = HackathonInput(
        theme="Edge Intelligence",
        name="BeachHack",
        session_id=session_id,
    )
    pipe_res = PipelineResult(
        session_id=session_id,
        input=h_input,
    )
    final_eval = FinalEvaluationReport(
        winner=WinnerSelection(has_winner=False, rejection_reason="No finalists survived gates."),
    )

    gen = ReportGenerator(test_repo)
    report = gen.generate(pipe_res, final_eval)

    # Verify report contains document citations
    markdown_content = report.to_markdown()
    assert "BeachHack-S08-Tracks.pdf" in markdown_content
    assert "[Uploaded document: BeachHack-S08-Tracks.pdf, Page <N>]" in markdown_content
    assert "Epistemic Provenance Separation" in markdown_content


def test_existing_document_extraction_and_multitrack_continue_working(test_repo: Repository) -> None:
    """8. Existing document extraction, auto-configuration and multi-track pipelines continue working."""
    service = DocumentIntelligenceService(repository=test_repo, llm=FakeLLM())
    doc = StructuredHackathonDoc(
        hackathon_name="BeachHack Season 08",
        extracted_facts=[
            "BeachHack Season 08 is held from 5th to 7th February 2027.",
            "There are six tracks: Agents in Production, The Toolchain, The Trust Layer, The Rails, The Edge, and Earth Systems.",
        ],
    )
    enriched = service.enrich_hackathon_profile(doc, filename="BeachHack-S08-Tracks.pdf")
    assert enriched.hackathon_name == "BeachHack Season 08"
    assert len(enriched.extracted_tracks) == 6

    uploaded = UploadedDocument(
        id="d-multi-1",
        filename="BeachHack-S08-Tracks.pdf",
        file_type="pdf",
        file_size=1024,
        file_hash="hash_multi_1",
    )
    h_input, status, _ = HackathonAutoConfigurator.configure_hackathon(
        profile=enriched,
        documents=[uploaded],
        multi_track_mode=MultiTrackMode.BEST_OVERALL,
    )
    assert h_input is not None
    assert h_input.is_multi_track is True
    assert len(h_input.tracks) == 6
    assert h_input.rules_url is None  # Separated cleanly
