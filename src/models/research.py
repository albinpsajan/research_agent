"""Pydantic models for research and existing solution analysis."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from src.utils.hackathon_time import utc_now


class SourceType(StrEnum):
    GITHUB = "github"
    ARXIV = "arxiv"
    OPENALEX = "openalex"
    CROSSREF = "crossref"
    RSS = "rss"
    WEB = "web"
    HACKATHON = "hackathon"
    PRODUCT = "product"
    PATENT = "patent"


class PublicationCategory(StrEnum):
    """Categorization of publication type and academic standing."""

    PREPRINT = "preprint"  # e.g., arXiv (not verified as peer-reviewed unless corroborated)
    SCHOLARLY_METADATA = "scholarly_metadata"  # e.g., Crossref/OpenAlex DOI record
    PEER_REVIEWED = "peer_reviewed"  # Explicitly corroborated peer-reviewed publication
    NEWS_COMMENTARY = "news_commentary"  # RSS bulletins, MIT News, ScienceDaily
    SOFTWARE_PROJECT = "software_project"  # GitHub repositories / open-source code
    WEB_RESOURCE = "web_resource"  # General web pages, blogs, discussion threads


class VerificationLevel(StrEnum):
    """Rigorous verification levels distinguishing raw hits from verified claims."""

    RETRIEVED_RECORD = "retrieved_record"  # Raw record returned from search endpoint
    METADATA_VALIDATED = "metadata_validated"  # Valid DOI / arXiv ID / URL structure confirmed
    RESOLVED_ACCESSIBLE = "resolved_accessible"  # Resolved and confirmed reachable (HTTP 200)
    CONTENT_INSPECTED = "content_inspected"  # Abstract, readme, or text content inspected
    INDEPENDENTLY_CORROBORATED = "independently_corroborated"  # Corroborated by >=2 independent sources


class ResearchSource(BaseModel):
    """A tracked research source with provenance."""

    url: str
    title: str
    source_type: SourceType
    retrieved_at: datetime = Field(default_factory=utc_now)
    description: str | None = None
    publication_category: PublicationCategory = PublicationCategory.WEB_RESOURCE
    verification_level: VerificationLevel = VerificationLevel.RETRIEVED_RECORD
    metadata: dict[str, Any] = Field(default_factory=dict)
    reliability: float = Field(default=0.5, ge=0, le=1)


class GitHubProject(BaseModel):
    """GitHub repository analysis."""

    url: str
    name: str
    description: str | None = None
    stars: int = 0
    forks: int = 0
    language: str | None = None
    last_updated: datetime | None = None
    topics: list[str] = Field(default_factory=list)
    is_active: bool = True
    documentation_quality: str = "unknown"
    functionality_summary: str | None = None
    limitations: list[str] = Field(default_factory=list)


class ExistingSolution(BaseModel):
    """An existing solution to a problem candidate."""

    name: str
    solution_type: (
        str  # "open_source", "commercial", "startup", "research", "hackathon_project"
    )
    description: str
    url: str | None = None
    what_it_solves: str = ""
    target_users: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    disadvantages: list[str] = Field(default_factory=list)
    unsolved_aspects: list[str] = Field(default_factory=list)
    missing_features: list[str] = Field(default_factory=list)
    adoption_barriers: list[str] = Field(default_factory=list)
    source: ResearchSource | None = None


class OpportunityClassification(StrEnum):
    COMMONLY_SOLVED = "commonly_solved"
    PARTIALLY_SOLVED = "partially_solved"
    LIMITED_SOLUTION = "existing_solution_with_important_limitations"
    UNDERSERVED = "underserved_problem"
    DIFFERENTIATED = "potentially_differentiated_opportunity"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AdaptabilityClassification(StrEnum):
    """Five-tier global-to-local transferability classification."""

    TIER_A_DIRECT = "tier_a_directly_transferable"  # Applicable with minimal change: data/API swap only
    TIER_B_MODIFIED = "tier_b_adaptable_with_modifications"  # Requires adaptation: local data, language, institutional context
    TIER_C_REDESIGN = "tier_c_requires_fundamental_redesign"  # Concept viable, but physical/institutional realities require redesign
    TIER_D_NON_TRANSFERABLE = "tier_d_non_transferable"  # Inapplicable due to climate, infrastructure, legal, or geographic incompatibility
    TIER_E_LOCALLY_ORIGINATED = "tier_e_locally_originated"  # Native innovation born from local conditions, no direct global analogue


class GlobalToLocalAdaptation(BaseModel):
    """Rigorous mapping from international innovation to Kerala and Indian localization."""

    global_reference_solution: str = ""
    global_source_url: str | None = None
    transferability_tier: AdaptabilityClassification = AdaptabilityClassification.TIER_B_MODIFIED
    kerala_applicability: str = ""
    india_scale_potential: str = ""
    required_modifications: list[str] = Field(default_factory=list)
    local_constraints: list[str] = Field(default_factory=list)


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
