"""Pydantic models and enums for the Hackathon Playbook Knowledge Base."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PlaybookCategory(StrEnum):
    """Core categories of hackathon lessons learned from real competitions."""

    THEME_DECONSTRUCTION = "theme_deconstruction"
    PROBLEM_SELECTION = "problem_selection"
    TECHNICAL_ARCHITECTURE = "technical_architecture"
    DEMO_ENGINEERING = "demo_engineering"
    ADVERSARIAL_DEFENSE = "adversarial_defense"
    WINNER_PATTERNS = "winner_patterns"
    FAILURE_MODES = "failure_modes"
    LOCALIZATION_STRATEGY = "localization_strategy"


class PlaybookProvenanceType(StrEnum):
    """Classification of the original knowledge source."""

    OFFICIAL_CRITERIA = "official_criteria"
    PARTICIPANT_GUIDE = "participant_guide"
    JUDGE_RETROSPECTIVE = "judge_retrospective"
    ENGINEERING_LESSON = "engineering_lesson"


class PlaybookEntry(BaseModel):
    """A structured lesson learned from hackathon judges, organizers, and winners."""

    id: str
    category: PlaybookCategory
    title: str
    source_origin: str  # e.g., "devpost_judging_guide", "mlh_playbook", "youtube_retrospective", "bread04_hackathon_guide", "microsoft_agent_academy"
    lesson: str
    actionable_guidance: str
    target_agent: str  # "agent_1_intelligence", "agent_2_domain", "agent_3_research", "agent_4_solution", "agent_5_critic", "all"
    kerala_india_applicability: str = ""
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)

    # Provenance tracking
    provenance_type: str = PlaybookProvenanceType.OFFICIAL_CRITERIA.value
    source_url: str = ""
    author_or_creator: str = ""
    publication_date: str = ""
    transcript_available: bool = False
    readme_reference: str = ""
