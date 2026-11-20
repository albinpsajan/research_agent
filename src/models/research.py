"""Pydantic models for research and existing solution analysis."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
from src.utils.hackathon_time import utc_now


class SourceType(str, Enum):
    GITHUB = "github"
    ARXIV = "arxiv"
    OPENALEX = "openalex"
    CROSSREF = "crossref"
    RSS = "rss"
    WEB = "web"
    HACKATHON = "hackathon"
    PRODUCT = "product"
    PATENT = "patent"


class ResearchSource(BaseModel):
    """A tracked research source with provenance."""
    url: str
    title: str
    source_type: SourceType
    retrieved_at: datetime = Field(default_factory=utc_now)
    description: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    reliability: float = Field(default=0.5, ge=0, le=1)


class GitHubProject(BaseModel):
    """GitHub repository analysis."""
    url: str
    name: str
    description: Optional[str] = None
    stars: int = 0
    forks: int = 0
    language: Optional[str] = None
    last_updated: Optional[datetime] = None
    topics: list[str] = Field(default_factory=list)
    is_active: bool = True
    documentation_quality: str = "unknown"
    functionality_summary: Optional[str] = None
    limitations: list[str] = Field(default_factory=list)


class ExistingSolution(BaseModel):
    """An existing solution to a problem candidate."""
    name: str
    solution_type: str  # "open_source", "commercial", "startup", "research", "hackathon_project"
    description: str
    url: Optional[str] = None
    what_it_solves: str = ""
    target_users: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    disadvantages: list[str] = Field(default_factory=list)
    unsolved_aspects: list[str] = Field(default_factory=list)
    missing_features: list[str] = Field(default_factory=list)
    adoption_barriers: list[str] = Field(default_factory=list)
    source: Optional[ResearchSource] = None


class OpportunityClassification(str, Enum):
    COMMONLY_SOLVED = "commonly_solved"
    PARTIALLY_SOLVED = "partially_solved"
    LIMITED_SOLUTION = "existing_solution_with_important_limitations"
    UNDERSERVED = "underserved_problem"
    DIFFERENTIATED = "potentially_differentiated_opportunity"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class InnovationGap(BaseModel):
    """An identified gap in existing solutions."""
    problem_candidate_id: str
    classification: OpportunityClassification
    existing_solutions: list[ExistingSolution] = Field(default_factory=list)
    github_projects: list[GitHubProject] = Field(default_factory=list)
    gap_description: str = ""
    differentiation_potential: str = ""
    evidence_summary: str = ""
    research_sources: list[ResearchSource] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class InnovationReport(BaseModel):
    """Complete existing solutions and innovation gap report."""
    gaps: list[InnovationGap] = Field(default_factory=list)
    total_solutions_found: int = 0
    total_github_projects: int = 0
    research_papers_reviewed: int = 0
    generated_at: datetime = Field(default_factory=utc_now)
