"""End-to-end pipeline result models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.models.candidate import FeasibilityReport
from src.models.domain import DomainMap
from src.models.evaluation import DebateHistory, WinnerSelection
from src.models.hackathon import HackathonInput, HackathonIntelligence
from src.models.report import FinalReport
from src.models.research import InnovationReport
from src.utils.hackathon_time import utc_now


class PipelineOptions(BaseModel):
    """Runtime knobs exposed to the UI (bounded research budgets, dynamic discovery)."""

    max_domains: int | None = Field(
        default=None,
        description="Optional legacy cap. When None, domain discovery is fully dynamic and relevance-driven.",
    )
    domain_exploration_budget: int = Field(
        default=15,
        ge=4,
        le=35,
        description="Exploration budget for domain discovery before stopping.",
    )
    min_domain_relevance: float = Field(
        default=0.45,
        ge=0.1,
        le=1.0,
        description="Minimum relevance score required for domain retention and expansion.",
    )
    problems_per_domain: int = Field(default=2, ge=1, le=5)
    max_finalists: int = Field(default=5, ge=2, le=10)
    max_debate_rounds: int = Field(default=3, ge=1, le=5)
    include_continuous_intelligence: bool = True


class PipelineResult(BaseModel):
    """Everything produced by one complete HackathonIQ run."""

    session_id: str
    input: HackathonInput
    intelligence: HackathonIntelligence | None = None
    domain_map: DomainMap | None = None
    innovation_report: InnovationReport | None = None
    feasibility: FeasibilityReport | None = None
    debates: list[DebateHistory] = Field(default_factory=list)
    winner: WinnerSelection | None = None
    report: FinalReport | None = None
    status: str = "completed"
    error: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    duration_seconds: float = 0.0

    def finalize(self) -> None:
        self.completed_at = utc_now()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
