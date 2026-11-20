"""Pydantic models for evaluation, scoring, and quality gates."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from src.utils.hackathon_time import utc_now


class QualityGateStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    NOT_EVALUATED = "not_evaluated"


class QualityGate(BaseModel):
    """A mandatory quality gate check."""

    name: str
    description: str
    status: QualityGateStatus = QualityGateStatus.NOT_EVALUATED
    justification: str = ""
    evidence: list[str] = Field(default_factory=list)


class ScoreCriterion(BaseModel):
    """A single scoring criterion with justification."""

    name: str
    weight: int
    score: float = Field(default=0, ge=0, le=10)
    weighted_score: float = 0
    justification: str = ""
    evidence: list[str] = Field(default_factory=list)


class CandidateEvaluation(BaseModel):
    """Complete evaluation of a candidate solution."""

    candidate_id: str
    candidate_title: str
    domain: str
    scores: list[ScoreCriterion] = Field(default_factory=list)
    base_score: float = 0
    debate_adjustment: float = 0
    total_score: float = 0
    quality_gates: list[QualityGate] = Field(default_factory=list)
    all_gates_passed: bool = False
    overall_assessment: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    debate_recommendation: str = ""
    is_qualified: bool = False
    rank: int | None = None

    def calculate_total(self) -> None:
        """Calculate base weighted score, gates, and post-debate total."""
        self.base_score = round(sum(s.weighted_score for s in self.scores), 2)
        self.total_score = round(
            max(0.0, min(100.0, self.base_score + self.debate_adjustment)), 2
        )
        self.all_gates_passed = all(
            g.status == QualityGateStatus.PASSED for g in self.quality_gates
        )
        self.is_qualified = (
            self.all_gates_passed
            and self.total_score > 0
            and self.debate_recommendation != "reject"
        )


class DebateRound(BaseModel):
    """A single round of adversarial debate."""

    round_number: int
    candidate_id: str
    criticism: str
    rebuttal: str
    evidence_provided: list[str] = Field(default_factory=list)
    criticism_resolved: bool = False
    score_adjustment: float = 0
    notes: str = ""


class DebateHistory(BaseModel):
    """Complete debate history for a candidate."""

    candidate_id: str
    rounds: list[DebateRound] = Field(default_factory=list)
    final_assessment: str = ""
    score_before_debate: float = 0
    score_after_debate: float = 0
    recommendation: str = ""  # "advance", "downgrade", "reject"


class WinnerSelection(BaseModel):
    """Final winner selection result."""

    has_winner: bool = False
    winner: CandidateEvaluation | None = None
    winner_solution: str | None = None  # JSON reference to CandidateSolution
    runner_ups: list[CandidateEvaluation] = Field(default_factory=list)
    rejection_reason: str | None = None
    debate_summary: str = ""
    selection_methodology: str = ""
    total_candidates_evaluated: int = 0
    total_candidates_rejected: int = 0
    generated_at: datetime = Field(default_factory=utc_now)


class FinalEvaluationReport(BaseModel):
    """Independent Final Evaluation Report produced by Agent 5."""

    evaluations: list[CandidateEvaluation] = Field(default_factory=list)
    debates: list[DebateHistory] = Field(default_factory=list)
    winner: WinnerSelection = Field(default_factory=WinnerSelection)
    scoring_methodology: str = ""
    generated_at: datetime = Field(default_factory=utc_now)
