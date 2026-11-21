"""Unit tests for the Hackathon Playbook Knowledge Base Subsystem."""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.knowledge.hackathon_playbook.database import PlaybookDatabase
from src.knowledge.hackathon_playbook.schema import PlaybookCategory, PlaybookEntry
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
    )
    assert entry.id == "TEST-001"
    assert entry.category == PlaybookCategory.WINNER_PATTERNS
    assert entry.confidence == 0.95
    assert len(entry.tags) == 2


def test_playbook_database_in_memory_and_seeding():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_playbook.db"
        db = PlaybookDatabase(db_path)
        all_entries = db.list_all()
        assert len(all_entries) == len(PLAYBOOK_SEED_ENTRIES)
        assert len(all_entries) >= 20

        # Verify specific seed item exists
        entry_001 = db.get_by_id("HP-001")
        assert entry_001 is not None
        assert entry_001.category == PlaybookCategory.THEME_DECONSTRUCTION


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
