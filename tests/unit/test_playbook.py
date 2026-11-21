"""Unit tests for the Hackathon Playbook Knowledge Base Subsystem."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.knowledge.hackathon_playbook.database import PlaybookDatabase
from src.knowledge.hackathon_playbook.ingestion import (
    GitHubPlaybookIngester,
    WebsitePlaybookIngester,
    YouTubePlaybookIngester,
)
from src.knowledge.hackathon_playbook.schema import (
    PlaybookCategory,
    PlaybookEntry,
    PlaybookProvenanceType,
)
from src.knowledge.hackathon_playbook.seed_data import PLAYBOOK_SEED_ENTRIES
from src.knowledge.hackathon_playbook.service import HackathonPlaybookService


def test_playbook_schema_validation():
    entry = PlaybookEntry(
        id="TEST-001",
        category=PlaybookCategory.WINNER_PATTERNS,
        title="Test Entry",
        source_origin="devpost_judging_guide",
        lesson="Judges prefer working demos.",
        actionable_guidance="Focus on core hero flow.",
        target_agent="agent_4_solution",
        kerala_india_applicability="Applicable to student hackathons in Kerala.",
        tags=["demo", "hero_flow"],
        confidence=0.95,
        provenance_type=PlaybookProvenanceType.OFFICIAL_CRITERIA.value,
        source_url="https://help.devpost.com/hc/en-us/articles/360017887751-Judging-criteria",
        author_or_creator="Devpost Team",
        publication_date="2023-11-15",
    )
    assert entry.id == "TEST-001"
    assert entry.category == PlaybookCategory.WINNER_PATTERNS
    assert entry.confidence == 0.95
    assert len(entry.tags) == 2
    assert entry.provenance_type == PlaybookProvenanceType.OFFICIAL_CRITERIA.value
    assert "devpost.com" in entry.source_url


def test_all_28_seed_entries_have_verified_provenance():
    assert len(PLAYBOOK_SEED_ENTRIES) == 28

    by_provenance: dict[str, int] = {}
    for entry in PLAYBOOK_SEED_ENTRIES:
        assert entry.id.startswith("HP-")
        assert len(entry.title) > 5
        assert len(entry.lesson) > 20
        assert len(entry.actionable_guidance) > 20
        assert len(entry.source_url) > 0
        assert len(entry.author_or_creator) > 0
        assert len(entry.publication_date) > 0
        assert entry.provenance_type in {
            PlaybookProvenanceType.OFFICIAL_CRITERIA.value,
            PlaybookProvenanceType.PARTICIPANT_GUIDE.value,
            PlaybookProvenanceType.JUDGE_RETROSPECTIVE.value,
            PlaybookProvenanceType.ENGINEERING_LESSON.value,
        }
        by_provenance[entry.provenance_type] = by_provenance.get(entry.provenance_type, 0) + 1

    # Exact breakdown check
    assert by_provenance[PlaybookProvenanceType.OFFICIAL_CRITERIA.value] == 8
    assert by_provenance[PlaybookProvenanceType.PARTICIPANT_GUIDE.value] == 7
    assert by_provenance[PlaybookProvenanceType.JUDGE_RETROSPECTIVE.value] == 9
    assert by_provenance[PlaybookProvenanceType.ENGINEERING_LESSON.value] == 4


def test_playbook_database_in_memory_and_seeding():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_playbook.db"
        db = PlaybookDatabase(db_path)
        all_entries = db.list_all()
        assert len(all_entries) == len(PLAYBOOK_SEED_ENTRIES)
        assert len(all_entries) == 28

        # Verify specific seed item exists with provenance
        entry_001 = db.get_by_id("HP-001")
        assert entry_001 is not None
        assert entry_001.category == PlaybookCategory.THEME_DECONSTRUCTION
        assert entry_001.provenance_type == PlaybookProvenanceType.OFFICIAL_CRITERIA.value
        assert "devpost.com" in entry_001.source_url
        assert "Devpost" in entry_001.author_or_creator


def test_playbook_fts5_search_and_category_filtering():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_playbook.db"
        db = PlaybookDatabase(db_path)

        # Search for offline
        results = db.search("offline architecture sqlite", limit=5)
        assert len(results) > 0
        assert any("offline" in r.lesson.lower() or "offline" in r.actionable_guidance.lower() for r in results)

        # Search with target agent
        critic_results = db.search("audit", target_agent="agent_5_critic", limit=5)
        assert len(critic_results) > 0
        assert all(r.target_agent in {"agent_5_critic", "all"} for r in critic_results)


def test_agent_tailored_retrieval_and_formatting():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_playbook.db"
        db = PlaybookDatabase(db_path)
        service = HackathonPlaybookService(db)

        # Agent 1
        a1_entries = service.retrieve_for_intelligence("Agriculture and Climate")
        assert len(a1_entries) > 0
        assert any(e.target_agent in {"agent_1_intelligence", "all"} for e in a1_entries)

        # Agent 2
        a2_entries = service.retrieve_for_domain_discovery("Climate-Resilient Agriculture")
        assert len(a2_entries) > 0

        # Agent 3
        a3_entries = service.retrieve_for_innovation_research("Agroforestry")
        assert len(a3_entries) > 0

        # Agent 4
        a4_entries = service.retrieve_for_solution_architect("Agroforestry", hours=36.0)
        assert len(a4_entries) > 0

        # Agent 5
        a5_entries = service.retrieve_for_adversarial_critic("AI Agroforestry System")
        assert len(a5_entries) > 0

        # Format prompt
        formatted = service.format_guidance_for_prompt(a1_entries)
        assert "HACKATHON PLAYBOOK INTELLIGENCE & HEURISTICS:" in formatted
        assert len(formatted) > 50


def test_youtube_ingester_url_parsing_and_caption_check():
    ingester = YouTubePlaybookIngester()

    # URL ID parsing
    vid1 = ingester.extract_video_id("https://www.youtube.com/watch?v=kYJmQ63c4g8")
    assert vid1 == "kYJmQ63c4g8"
    vid2 = ingester.extract_video_id("https://youtu.be/kYJmQ63c4g8?t=10")
    assert vid2 == "kYJmQ63c4g8"
    vid3 = ingester.extract_video_id("https://www.youtube.com/embed/kYJmQ63c4g8")
    assert vid3 == "kYJmQ63c4g8"
    assert ingester.extract_video_id("https://example.com/not_youtube") is None

    # Offline/mock check of transcript inspection
    with patch("urllib.request.urlopen") as mock_urlopen:
        # Mock HTML without captionTracks
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html><body><div>No captions here</div></body></html>"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = ingester.check_transcript_availability("https://www.youtube.com/watch?v=kYJmQ63c4g8")
        assert res["transcript_available"] is False
        assert res["transcript_status"] == "unavailable_or_disabled"
        assert res["caption_tracks_found"] is False


def test_youtube_ingester_entry_creation():
    ingester = YouTubePlaybookIngester()
    with patch.object(ingester, "fetch_oembed_metadata", return_value={"title": "Judge Tips", "author_name": "Devpost Panel", "status": "success"}):
        with patch.object(ingester, "check_transcript_availability", return_value={"transcript_available": False, "transcript_status": "unavailable_or_disabled"}):
            entry = ingester.ingest_retrospective(
                url="https://www.youtube.com/watch?v=kYJmQ63c4g8",
                lesson_title="Hero Flow First",
                lesson="Don't spend 5 minutes logging in during 3 minute demo.",
                actionable_guidance="Build 1-click test user.",
                target_agent="agent_4_solution",
                category=PlaybookCategory.DEMO_ENGINEERING,
            )

            assert entry.provenance_type == PlaybookProvenanceType.JUDGE_RETROSPECTIVE.value
            assert entry.author_or_creator == "Devpost Panel"
            assert entry.source_url == "https://www.youtube.com/watch?v=kYJmQ63c4g8"
            assert entry.transcript_available is False


def test_website_ingester_entry_creation():
    ingester = WebsitePlaybookIngester()
    with patch.object(ingester, "fetch_article_metadata", return_value={"title": "MLH Rules", "author": "MLH Staff", "published_date": "2024-01-01", "status": "success"}):
        entry = ingester.ingest_guide(
            url="https://github.com/MLH/mlh-hackathon-playbook",
            lesson_title="Judging Matrix",
            lesson="Always provide a competitive comparison matrix.",
            actionable_guidance="List 3 competitor tools and why this solution is better.",
            target_agent="agent_3_research",
            category=PlaybookCategory.WINNER_PATTERNS,
            provenance_type=PlaybookProvenanceType.PARTICIPANT_GUIDE,
            source_origin="mlh_playbook",
        )

        assert entry.provenance_type == PlaybookProvenanceType.PARTICIPANT_GUIDE.value
        assert entry.author_or_creator == "MLH Staff"
        assert entry.category == PlaybookCategory.WINNER_PATTERNS


def test_github_ingester_parsing_and_winner_detection():
    ingester = GitHubPlaybookIngester()

    # Slug parsing
    owner, repo = ingester.parse_repo_slug("https://github.com/microsoft/agent-academy")
    assert owner == "microsoft"
    assert repo == "agent-academy"

    owner2, repo2 = ingester.parse_repo_slug("bread04/hackAthon-gUide")
    assert owner2 == "bread04"
    assert repo2 == "hackAthon-gUide"

    # Analyze README mock with winner accolades
    sample_readme = """
    # SmartAgri - 1st Place Winner at Devpost Climate Hackathon 2024
    An offline-first architecture using SQLite and local ML models.
    ## Architecture
    The data flow processes local sensor inputs.
    """
    with patch.object(ingester, "fetch_readme", return_value=sample_readme):
        analysis = ingester.analyze_winner_repository("team/smartagri")
        assert analysis["is_winner_verified"] is True
        assert analysis["features_offline"] is True
        assert analysis["has_architecture_section"] is True

        entry = ingester.ingest_winner_repo(
            repo_url="https://github.com/team/smartagri",
            lesson_title="Offline-first for Agri Hackathons",
            lesson="Offline architecture won first place in climate track.",
            actionable_guidance="Use SQLite and local caches.",
            target_agent="agent_4_solution",
        )
        assert entry.provenance_type == PlaybookProvenanceType.ENGINEERING_LESSON.value
        assert "verified_winner" in entry.tags
        assert entry.author_or_creator == "team"
