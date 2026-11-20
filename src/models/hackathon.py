"""Pydantic models for hackathon intelligence data."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl
from src.utils.hackathon_time import utc_now


class HackathonInput(BaseModel):
    """User input for a hackathon research session."""
    theme: str = Field(..., min_length=3, description="Hackathon theme")
    name: Optional[str] = Field(default=None, description="Hackathon name")
    website_url: Optional[str] = Field(default=None, description="Official website URL")
    rules_url: Optional[str] = Field(default=None, description="Rules page URL")
    deadline: Optional[datetime] = Field(default=None, description="Submission deadline")
    constraints: Optional[str] = Field(default=None, description="Additional constraints")
    session_id: Optional[str] = Field(default=None, description="Session identifier")


class OrganizerProfile(BaseModel):
    """Profile of the hackathon organizing institution."""
    name: str
    mission: Optional[str] = None
    ideology: Optional[str] = None
    objectives: list[str] = Field(default_factory=list)
    website: Optional[str] = None
    source_urls: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class JudgeProfile(BaseModel):
    """Profile of a hackathon judge."""
    name: str
    expertise: list[str] = Field(default_factory=list)
    organization: Optional[str] = None
    source_url: Optional[str] = None


class SponsorProfile(BaseModel):
    """Profile of a hackathon sponsor."""
    name: str
    interests: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    initiatives: list[str] = Field(default_factory=list)
    source_url: Optional[str] = None


class PreviousProject(BaseModel):
    """Previous hackathon project/submission."""
    title: str
    description: Optional[str] = None
    year: Optional[int] = None
    placement: Optional[str] = None  # "winner", "finalist", "submission"
    technologies: list[str] = Field(default_factory=list)
    source_url: Optional[str] = None


class JudgingCriteria(BaseModel):
    """Official judging criteria."""
    criterion: str
    weight: Optional[float] = None
    description: Optional[str] = None


class HackathonIntelligence(BaseModel):
    """Complete hackathon intelligence report."""
    hackathon_input: HackathonInput
    organizer: Optional[OrganizerProfile] = None
    judges: list[JudgeProfile] = Field(default_factory=list)
    sponsors: list[SponsorProfile] = Field(default_factory=list)
    previous_projects: list[PreviousProject] = Field(default_factory=list)
    judging_criteria: list[JudgingCriteria] = Field(default_factory=list)
    submission_requirements: list[str] = Field(default_factory=list)
    technical_restrictions: list[str] = Field(default_factory=list)
    time_limit_hours: Optional[float] = None
    target_participants: Optional[str] = None
    expected_outcomes: list[str] = Field(default_factory=list)
    organizer_goals: list[str] = Field(default_factory=list)
    recurring_priorities: list[str] = Field(default_factory=list)
    verified_facts: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    research_sources: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)
