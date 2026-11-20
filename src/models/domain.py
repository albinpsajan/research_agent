"""Pydantic models for dynamic domain discovery."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from src.utils.hackathon_time import utc_now


class DomainRelevance(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    INTERDISCIPLINARY = "interdisciplinary"
    EMERGING = "emerging"


class DiscoveredDomain(BaseModel):
    """A dynamically discovered domain relevant to the hackathon theme."""
    name: str
    description: str
    relevance_type: DomainRelevance
    relevance_explanation: str
    subdomains: list[str] = Field(default_factory=list)
    connections_to_theme: list[str] = Field(default_factory=list)
    interdisciplinary_links: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class ProblemEvidence(BaseModel):
    """Evidence supporting the existence of a real-world problem."""
    description: str
    source_url: Optional[str] = None
    source_type: str = "general"  # "research", "news", "statistics", "government", "industry"
    retrieved_at: Optional[datetime] = None
    credibility: float = Field(default=0.5, ge=0, le=1)


class ProblemCandidate(BaseModel):
    """A discovered real-world problem candidate."""
    id: Optional[str] = None
    title: str
    description: str
    domain: str
    subdomain: Optional[str] = None
    affected_people: list[str] = Field(default_factory=list)
    seriousness: str = "moderate"  # "low", "moderate", "high", "critical"
    evidence: list[ProblemEvidence] = Field(default_factory=list)
    inadequate_solutions: list[str] = Field(default_factory=list)
    overlooked_needs: list[str] = Field(default_factory=list)
    emerging_opportunities: list[str] = Field(default_factory=list)
    future_potential: list[str] = Field(default_factory=list)
    theme_connection: str = ""
    is_generic: bool = False
    confidence: float = Field(default=0.5, ge=0, le=1)


class DomainMap(BaseModel):
    """Complete domain discovery results."""
    theme: str
    domains: list[DiscoveredDomain] = Field(default_factory=list)
    problem_candidates: list[ProblemCandidate] = Field(default_factory=list)
    total_domains_explored: int = 0
    total_problems_found: int = 0
    generated_at: datetime = Field(default_factory=utc_now)
