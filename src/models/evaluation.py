"""Pydantic models for evaluation, scoring, and quality gates."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from src.utils.hackathon_time import utc_now


class QualityGateStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    NOT_EVALUATED = "not_evaluated"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"


class EvaluationVersion(StrEnum):
    """Evaluation framework version distinguishing historical 7-gate runs from 10-gate master runs."""

    V1_SEVEN_GATE = "v1_seven_gate"
    V2_TEN_GATE = "v2_ten_gate"


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
    raw_score: float = 0.0
    normalized_score: float = 0.0
    is_general_theme_mode: bool = False
    evaluation_version: EvaluationVersion = EvaluationVersion.V2_TEN_GATE
    quality_gates: list[QualityGate] = Field(default_factory=list)
    all_gates_passed: bool = False
    overall_assessment: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    debate_recommendation: str = ""
    is_qualified: bool = False
    rank: int | None = None
    improvement_rounds_attempted: int = 0
    elimination_reason: str | None = None

    @model_validator(mode="before")
    @classmethod
    def detect_version_from_gates(cls, data: Any) -> Any:
        if isinstance(data, dict):
            gates = data.get("quality_gates") or []
            if len(gates) == 7 and "evaluation_version" not in data:
                data["evaluation_version"] = EvaluationVersion.V1_SEVEN_GATE
        return data

    def calculate_total(self) -> None:
        """Calculate base weighted score, gates, and post-debate total."""
        self.raw_score = round(sum(s.weighted_score for s in self.scores), 2)
        if self.is_general_theme_mode:
            # Organizer and sponsor alignment (10 pts) is not assessable (0 raw out of 90)
            # Normalized to 100-point scale: (raw / 90) * 100
            assessable_weight = sum(s.weight for s in self.scores if "organizer" not in s.name.lower() and "sponsor" not in s.name.lower())
            if assessable_weight > 0:
                self.normalized_score = round(min(100.0, (self.raw_score / assessable_weight) * 100.0), 2)
            else:
                self.normalized_score = self.raw_score
            self.base_score = self.raw_score
            self.total_score = round(
                max(0.0, min(100.0, self.normalized_score + self.debate_adjustment)), 2
            )
        else:
            self.base_score = self.raw_score
            self.normalized_score = self.base_score
            self.total_score = round(
                max(0.0, min(100.0, self.base_score + self.debate_adjustment)), 2
            )
        self.all_gates_passed = all(
            g.status in {QualityGateStatus.PASSED, QualityGateStatus.NOT_APPLICABLE}
            for g in self.quality_gates
        ) and any(g.status == QualityGateStatus.PASSED for g in self.quality_gates)
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
