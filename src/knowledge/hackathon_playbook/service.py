"""Service layer exposing Hackathon Playbook intelligence to the five agents."""

from __future__ import annotations

from typing import Sequence

from config.logging_config import get_logger
from src.knowledge.hackathon_playbook.database import PlaybookDatabase
from src.knowledge.hackathon_playbook.schema import PlaybookCategory, PlaybookEntry

logger = get_logger("knowledge.hackathon_playbook.service")


class HackathonPlaybookService:
    """Provides targeted hackathon playbook lessons and heuristics to each logical agent."""

    def __init__(self, db: PlaybookDatabase | None = None) -> None:
        self.db = db or PlaybookDatabase()

    def retrieve_for_intelligence(self, theme: str) -> list[PlaybookEntry]:
        """Retrieve theme deconstruction and judging alignment lessons for Agent 1."""
        entries = self.db.search(
            query=f"{theme} theme judging organizer rubric",
            target_agent="agent_1_intelligence",
            limit=4,
        )
        if not entries:
            entries = self.db.search(
                query="theme judging",
                category=PlaybookCategory.THEME_DECONSTRUCTION,
                limit=3,
            )
        return entries

    def retrieve_for_domain_discovery(self, theme: str) -> list[PlaybookEntry]:
        """Retrieve problem selection, niche sharpening, and Kerala localization lessons for Agent 2."""
        entries = self.db.search(
            query=f"{theme} problem niche kerala evidence smallholder",
            target_agent="agent_2_domain",
            limit=4,
        )
        if not entries:
            entries = self.db.search(
                query="problem niche",
                category=PlaybookCategory.PROBLEM_SELECTION,
                limit=3,
            )
        return entries

    def retrieve_for_innovation_research(self, domain: str) -> list[PlaybookEntry]:
        """Retrieve global research benchmarking, taxonomy, and wrapper avoidance lessons for Agent 3."""
        entries = self.db.search(
            query=f"{domain} global transferability adaptation wrapper competitive",
            target_agent="agent_3_research",
            limit=4,
        )
        if not entries:
            entries = self.db.search(
                query="global transferability",
                category=PlaybookCategory.WINNER_PATTERNS,
                limit=3,
            )
        return entries

    def retrieve_for_solution_architect(self, domain: str, hours: float = 36.0) -> list[PlaybookEntry]:
        """Retrieve buildability scoping, offline-first design, and demo pitch rules for Agent 4."""
        entries = self.db.search(
            query=f"{domain} architecture offline build demo 3-minute hero flow",
            target_agent="agent_4_solution",
            limit=4,
        )
        if not entries:
            entries = self.db.search(
                query="architecture demo",
                category=PlaybookCategory.TECHNICAL_ARCHITECTURE,
                limit=3,
            )
        return entries

    def retrieve_for_adversarial_critic(self, candidate_title: str) -> list[PlaybookEntry]:
        """Retrieve audit patterns, sensor geometry checks, and honest rejection standards for Agent 5."""
        entries = self.db.search(
            query=f"{candidate_title} audit resolution failure ground truth rejection literacy",
            target_agent="agent_5_critic",
            limit=4,
        )
        if not entries:
            entries = self.db.search(
                query="audit rejection",
                category=PlaybookCategory.ADVERSARIAL_DEFENSE,
                limit=3,
            )
        return entries

    @staticmethod
    def format_guidance_for_prompt(entries: Sequence[PlaybookEntry]) -> str:
        """Format playbook entries into an injectable prompt context string."""
        if not entries:
            return ""
        lines = ["HACKATHON PLAYBOOK INTELLIGENCE & HEURISTICS:"]
        for e in entries:
            lines.append(f"- [{e.category.value}] {e.title}: {e.lesson}")
            lines.append(f"  Guidance: {e.actionable_guidance}")
            if e.kerala_india_applicability:
                lines.append(f"  Regional Context: {e.kerala_india_applicability}")
        return "\n".join(lines)
