"""End-to-end pipeline result models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from src.models.candidate import FeasibilityReport
from src.models.domain import DomainMap
from src.models.evaluation import DebateHistory, WinnerSelection
from src.models.hackathon import HackathonInput, HackathonIntelligence
from src.models.report import FinalReport
from src.models.research import InnovationReport
from src.utils.hackathon_time import utc_now


class ResearchExecutionStatus(str, Enum):
    """Execution lifecycle status of a research session."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


class WinnerOutcome(str, Enum):
    """Independent evaluation outcome regarding candidate winners."""

    WINNER_SELECTED = "winner_selected"
    NO_QUALIFYING_WINNER = "no_qualifying_winner"
    NOT_EVALUATED = "not_evaluated"


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

    @property
    def final_report(self) -> FinalReport | None:
        """Alias property matching UI references."""
        return self.report

    @property
    def execution_status(self) -> ResearchExecutionStatus:
        """Explicit research execution status."""
        s = (self.status or "completed").lower()
        if s in ("running", "in_progress", "started"):
            return ResearchExecutionStatus.RUNNING
        elif s in ("pending", "created", "draft"):
            return ResearchExecutionStatus.PENDING
        elif s == "interrupted":
            return ResearchExecutionStatus.INTERRUPTED
        elif s == "failed":
            return ResearchExecutionStatus.FAILED
        else:
            return ResearchExecutionStatus.COMPLETED

    @property
    def winner_outcome(self) -> WinnerOutcome:
        """Explicit evaluation outcome, strictly separated from execution status."""
        if self.execution_status != ResearchExecutionStatus.COMPLETED:
            return WinnerOutcome.NOT_EVALUATED
        if self.winner and self.winner.has_winner and self.winner.winner:
            return WinnerOutcome.WINNER_SELECTED
        # Only declare NO_QUALIFYING_WINNER if evaluation was actually conducted
        if self.winner is not None or (self.report and self.report.has_winner is not None):
            return WinnerOutcome.NO_QUALIFYING_WINNER
        return WinnerOutcome.NOT_EVALUATED

    def finalize(self) -> None:
        self.completed_at = utc_now()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
