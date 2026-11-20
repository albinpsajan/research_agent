"""End-to-end pipeline result models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from src.utils.hackathon_time import utc_now

from src.models.candidate import FeasibilityReport
from src.models.domain import DomainMap
from src.models.evaluation import DebateHistory, WinnerSelection
from src.models.hackathon import HackathonInput, HackathonIntelligence
from src.models.report import FinalReport
from src.models.research import InnovationReport


class PipelineOptions(BaseModel):
    """Runtime knobs exposed to the UI (bounded, never unlimited)."""

    max_domains: int = Field(default=8, ge=3, le=20)
    problems_per_domain: int = Field(default=2, ge=1, le=5)
    max_finalists: int = Field(default=5, ge=2, le=10)
    max_debate_rounds: int = Field(default=3, ge=1, le=5)
    include_continuous_intelligence: bool = True


class PipelineResult(BaseModel):
    """Everything produced by one complete HackathonIQ run."""

    session_id: str
    input: HackathonInput
    intelligence: Optional[HackathonIntelligence] = None
    domain_map: Optional[DomainMap] = None
    innovation_report: Optional[InnovationReport] = None
    feasibility: Optional[FeasibilityReport] = None
    debates: list[DebateHistory] = Field(default_factory=list)
    winner: Optional[WinnerSelection] = None
    report: Optional[FinalReport] = None
    status: str = "completed"
    error: Optional[str] = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0

    def finalize(self) -> None:
        self.completed_at = utc_now()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
