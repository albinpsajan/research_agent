"""Pydantic models for hackathon intelligence data."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.models.provenance import CategorizedConstraint, ProvenanceCategory
from src.utils.hackathon_time import utc_now


class HackathonInput(BaseModel):
    """User input for a hackathon research session."""

    theme: str = Field(..., min_length=3, description="Hackathon theme")
    name: str | None = Field(default=None, description="Hackathon name")
    website_url: str | None = Field(default=None, description="Official website URL")
    rules_url: str | None = Field(default=None, description="Rules page URL")
    deadline: datetime | None = Field(default=None, description="Submission deadline")
    constraints: str | None = Field(default=None, description="Additional constraints")
    session_id: str | None = Field(default=None, description="Session identifier")


class OrganizerProfile(BaseModel):
    """Profile of the hackathon organizing institution."""

    name: str
    mission: str | None = None
    ideology: str | None = None
    objectives: list[str] = Field(default_factory=list)
    website: str | None = None
    source_urls: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class JudgeProfile(BaseModel):
    """Profile of a hackathon judge."""

    name: str
    expertise: list[str] = Field(default_factory=list)
    organization: str | None = None
    source_url: str | None = None


class SponsorProfile(BaseModel):
    """Profile of a hackathon sponsor."""

    name: str
    interests: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    initiatives: list[str] = Field(default_factory=list)
    source_url: str | None = None


class PreviousProject(BaseModel):
    """Previous hackathon project/submission."""

    title: str
    description: str | None = None
    year: int | None = None
    placement: str | None = None  # "winner", "finalist", "submission"
    technologies: list[str] = Field(default_factory=list)
    source_url: str | None = None


class JudgingCriteria(BaseModel):
    """Official judging criteria."""

    criterion: str
    weight: float | None = None
    description: str | None = None


class HackathonIntelligence(BaseModel):
    """Complete hackathon intelligence report."""

    hackathon_input: HackathonInput
    organizer: OrganizerProfile | None = None
    judges: list[JudgeProfile] = Field(default_factory=list)
    sponsors: list[SponsorProfile] = Field(default_factory=list)
    previous_projects: list[PreviousProject] = Field(default_factory=list)
    judging_criteria: list[JudgingCriteria] = Field(default_factory=list)
    submission_requirements: list[str] = Field(default_factory=list)
    technical_restrictions: list[str] = Field(default_factory=list)
    time_limit_hours: float | None = None
    target_participants: str | None = None
    expected_outcomes: list[str] = Field(default_factory=list)
    organizer_goals: list[str] = Field(default_factory=list)
    recurring_priorities: list[str] = Field(default_factory=list)
    categorized_constraints: list[CategorizedConstraint] = Field(default_factory=list)
    verified_facts: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    research_sources: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)
