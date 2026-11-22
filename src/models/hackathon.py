"""Pydantic models for hackathon intelligence data."""

from __future__ import annotations

import ipaddress
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlparse
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field, ValidationInfo, field_validator

from src.models.provenance import CategorizedConstraint
from src.utils.hackathon_time import utc_now

_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
}


def _validate_external_url(url: str | None, field_name: str = "URL") -> str | None:
    """Validate external public URL without blocking on network DNS resolution.

    Ensures that only valid HTTP or HTTPS URLs with valid hosts are accepted,
    strictly rejecting internal/unsupported schemes (e.g. 'doc://', 'ftp://'),
    embedded credentials, and localhost / private network addresses.
    Returns None if url is None or empty.
    """
    if url is None:
        return None
    if isinstance(url, str):
        clean = url.strip()
        if not clean:
            return None
        parsed = urlparse(clean)
        scheme = (parsed.scheme or "").lower()
        if scheme not in ("http", "https"):
            raise ValueError(
                f"Unsupported URL scheme: '{parsed.scheme}'. Only HTTP and HTTPS URLs are accepted for {field_name}."
            )
        if parsed.username or parsed.password:
            raise ValueError(f"{field_name} cannot contain embedded credentials")
        host = (parsed.hostname or "").lower()
        if not host:
            raise ValueError(f"Invalid {field_name}: missing hostname")
        if host in _BLOCKED_HOSTS or host.endswith(".local"):
            raise ValueError(f"Blocked host in {field_name}: {host}")
        try:
            ip = ipaddress.ip_address(host)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            ):
                raise ValueError(f"Private or reserved address blocked in {field_name}: {host}")
        except ValueError as err:
            if "blocked in" in str(err):
                raise
        return clean
    raise ValueError(f"{field_name} must be a valid string or None")


class MultiTrackMode(StrEnum):
    """User-selectable operating mode for multi-track hackathons."""

    BEST_OVERALL = "best_overall"  # Mode A: Single strongest project opportunity across all tracks
    BEST_PER_TRACK = "best_per_track"  # Mode B: Strongest qualifying project idea per track


class HackathonTrack(BaseModel):
    """An official track or theme within a multi-track hackathon."""

    id: str = Field(default_factory=lambda: f"TRK-{uuid4().hex[:6]}")
    name: str = Field(..., min_length=2, description="Track name")
    description: str | None = Field(default=None, description="Track description, scope or problem statement guidance")
    track_rules: str | None = Field(
        default=None,
        validation_alias=AliasChoices("track_rules", "rules"),
        description="Track-specific constraints, rules, or judging criteria",
    )
    official_track_url: str | None = Field(default=None, description="URL to official track documentation")

    @property
    def rules(self) -> str | None:
        """Alias property for compatibility with 'rules' parameter."""
        return self.track_rules

    @field_validator("official_track_url", mode="before")
    @classmethod
    def validate_track_url(cls, v: str | None) -> str | None:
        return _validate_external_url(v, field_name="official_track_url")


class HackathonInput(BaseModel):
    """User input for a hackathon research session."""

    theme: str = Field(..., min_length=3, description="Hackathon theme")
    name: str | None = Field(default=None, description="Hackathon name")
    website_url: str | None = Field(default=None, description="Official website URL")
    rules_url: str | None = Field(default=None, description="Rules page URL")
    deadline: datetime | None = Field(default=None, description="Submission deadline")
    constraints: str | None = Field(default=None, description="Additional constraints")
    session_id: str | None = Field(default=None, description="Session identifier")

    # Multi-track configuration
    is_multi_track: bool = Field(default=False, description="Whether this hackathon features multiple distinct tracks")
    multi_track_mode: MultiTrackMode = Field(
        default=MultiTrackMode.BEST_OVERALL,
        description="Operating mode: Best Overall Track (Mode A) or Best Idea Per Track (Mode B)",
    )
    tracks: list[HackathonTrack] = Field(default_factory=list, description="Supplied hackathon tracks")

    @field_validator("website_url", "rules_url", mode="before")
    @classmethod
    def validate_input_urls(cls, v: str | None, info: ValidationInfo) -> str | None:
        return _validate_external_url(v, field_name=info.field_name)


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
    is_general_theme_mode: bool = False
    generated_at: datetime = Field(default_factory=utc_now)
