"""Pydantic models for solution candidates and feasibility analysis."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.models.research import GlobalToLocalAdaptation
from src.utils.hackathon_time import utc_now


class TechnicalRequirement(BaseModel):
    """Technical requirement for a solution."""

    category: str  # "data", "api", "infrastructure", "library", "hardware"
    description: str
    availability: str = "unknown"  # "available", "limited", "restricted", "unavailable"
    cost: str = "free"  # "free", "freemium", "paid", "expensive"
    risk_level: str = "low"  # "low", "medium", "high"


class RiskAssessment(BaseModel):
    """Risk assessment for a candidate solution."""

    risk_type: str  # "technical", "practical", "timeline", "scope", "dependency"
    description: str
    severity: str = "medium"  # "low", "medium", "high", "critical"
    likelihood: str = "possible"  # "unlikely", "possible", "likely", "certain"
    mitigation: str | None = None


class CandidateSolution(BaseModel):
    """A refined candidate solution with feasibility analysis."""

    id: str | None = None
    title: str = ""
    problem_candidate_id: str
    problem_statement: str
    target_users: list[str] = Field(default_factory=list)
    user_pain_point: str = ""
    supporting_evidence: list[str] = Field(default_factory=list)
    supporting_evidence_urls: list[str] = Field(default_factory=list)
    existing_alternatives: list[str] = Field(default_factory=list)
    existing_solutions_compared: list[str] = Field(default_factory=list)
    identified_gap: str = ""
    proposed_solution: str = ""
    unique_differentiation: str = ""
    relevant_technologies: list[str] = Field(default_factory=list)
    data_requirements: list[TechnicalRequirement] = Field(default_factory=list)
    api_requirements: list[TechnicalRequirement] = Field(default_factory=list)
    technical_architecture: str = ""
    development_complexity: str = "medium"  # "low", "medium", "high", "very_high"
    estimated_hours: float | None = None
    infrastructure_requirements: list[str] = Field(default_factory=list)
    estimated_cost: str = "minimal"
    dependencies: list[str] = Field(default_factory=list)
    risks: list[RiskAssessment] = Field(default_factory=list)
    advantages: list[str] = Field(default_factory=list)
    disadvantages: list[str] = Field(default_factory=list)
    mitigation_strategies: list[str] = Field(default_factory=list)
    hackathon_demo_plan: str = ""
    kerala_adaptation: GlobalToLocalAdaptation | None = None
    target_geography: str = "kerala"
    target_districts: list[str] = Field(default_factory=list)
    economic_viability_notes: str = ""
    ethical_sustainability_notes: str = ""
    feasibility_score: float = Field(default=0.5, ge=0, le=1)
    is_rejected: bool = False
    rejection_reason: str | None = None
    domain: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence_confidence: float = Field(default=0.5, ge=0, le=1)
    failure_categories: list[str] = Field(default_factory=list)
    validation_notes: list[str] = Field(default_factory=list)


class FeasibilityReport(BaseModel):
    """Complete feasibility analysis report."""

    candidates: list[CandidateSolution] = Field(default_factory=list)
    rejected_candidates: list[CandidateSolution] = Field(default_factory=list)
    total_evaluated: int = 0
    generated_at: datetime = Field(default_factory=utc_now)
