"""Models for multi-track research, evaluation, and cross-track comparison."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.models.candidate import CandidateSolution, FeasibilityReport
from src.models.domain import DomainMap
from src.models.evaluation import (
    CandidateEvaluation,
    DebateHistory,
    WinnerSelection,
)
from src.models.hackathon import (
    HackathonInput,
    HackathonIntelligence,
    HackathonTrack,
    MultiTrackMode,
)
from src.models.report import FinalReport
from src.models.research import InnovationReport
from src.models.pipeline import ResearchExecutionStatus, WinnerOutcome
from src.utils.hackathon_time import utc_now


class TrackResult(BaseModel):
    """Execution output for an individual track within a multi-track hackathon."""

    track: HackathonTrack
    input: HackathonInput
    domain_map: DomainMap | None = None
    innovation_report: InnovationReport | None = None
    feasibility: FeasibilityReport | None = None
    debates: list[DebateHistory] = Field(default_factory=list)
    winner: WinnerSelection | None = None
    report: FinalReport | None = None
    report_path: str | None = None
    status: str = "completed"  # "completed", "completed_no_winner", "failed"
    error: str | None = None
    duration_seconds: float = 0.0

    @property
    def track_report(self) -> FinalReport | None:
        """Alias property matching UI expectations."""
        return self.report


class BestTrackWinnerItem(BaseModel):
    """Unified representation of a track's best candidate solution and evaluation."""

    candidate: CandidateSolution | None = None
    evaluation: CandidateEvaluation | None = None

    @property
    def has_winner(self) -> bool:
        return self.candidate is not None and self.evaluation is not None

    @property
    def candidate_title(self) -> str:
        if self.evaluation and self.evaluation.candidate_title:
            return self.evaluation.candidate_title
        if self.candidate and self.candidate.title:
            return self.candidate.title
        return ""

    @property
    def total_score(self) -> float:
        return self.evaluation.total_score if self.evaluation else 0.0


class CrossTrackComparisonItem(BaseModel):
    """Standardized representation of a candidate for cross-track ranking and comparison."""

    candidate_id: str
    candidate_title: str
    track_id: str
    track_name: str
    domain: str
    total_score: float
    raw_score: float
    normalized_score: float
    all_gates_passed: bool
    is_qualified: bool
    rank_overall: int | None = None
    rank_in_track: int | None = None

    # Criterion breakdown scores (0-10 scale for cross-track contrast)
    impact_score: float = 0.0
    originality_score: float = 0.0
    feasibility_score: float = 0.0
    relevance_score: float = 0.0
    organizer_alignment_score: float = 0.0
    evidence_strength_score: float = 0.0
    demo_potential_score: float = 0.0

    summary_justification: str = ""
    proposed_solution_preview: str = ""
    unique_differentiation: str = ""


class CrossTrackComparisonResult(BaseModel):
    """Complete cross-track ranking, duplicate analysis, and winner selection output."""

    mode: MultiTrackMode
    total_tracks: int = 0
    tracks_completed: int = 0
    tracks_failed: int = 0

    # Mode A (Best Overall Track) outputs
    overall_winning_track: HackathonTrack | None = None
    overall_winning_candidate: CandidateSolution | None = None
    overall_winner_evaluation: CandidateEvaluation | None = None

    # Mode B (Best Idea Per Track) outputs: track_id -> candidate / evaluation
    per_track_winners: dict[str, CandidateSolution | None] = Field(default_factory=dict)
    per_track_evaluations: dict[str, CandidateEvaluation | None] = Field(default_factory=dict)

    # Detailed cross-track tables
    ranked_candidates: list[CrossTrackComparisonItem] = Field(default_factory=list)
    rejected_candidates: list[CrossTrackComparisonItem] = Field(default_factory=list)

    selection_rationale: str = ""
    runner_ups_explanation: str = ""
    duplicate_detections: list[dict[str, Any]] = Field(default_factory=list)
    compared_at: datetime = Field(default_factory=utc_now)

    @property
    def best_per_track(self) -> dict[str, BestTrackWinnerItem]:
        """Accessor mapping track_id -> BestTrackWinnerItem for Mode B results."""
        result: dict[str, BestTrackWinnerItem] = {}
        all_track_ids = set(self.per_track_winners.keys()) | set(self.per_track_evaluations.keys())
        for tid in all_track_ids:
            cand = self.per_track_winners.get(tid)
            ev = self.per_track_evaluations.get(tid)
            result[tid] = BestTrackWinnerItem(candidate=cand, evaluation=ev)
        return result

    @property
    def runner_up_explanations(self) -> list[str]:
        """Accessor returning runner-up explanation lines as a list."""
        if not self.runner_ups_explanation:
            return []
        return [
            line.strip("- ").strip()
            for line in self.runner_ups_explanation.splitlines()
            if line.strip()
        ]

    @property
    def duplicate_resolutions(self) -> list[dict[str, Any]]:
        """Normalized duplicate resolutions list for UI presentation."""
        resolutions = []
        for d in self.duplicate_detections:
            cand_a = d.get("candidate_a_title", "")
            cand_b = d.get("candidate_b_title", "")
            track_a = d.get("track_a_name", "")
            track_b = d.get("track_b_name", "")
            best_track = d.get("best_fit_track_name", "")
            orig_track = track_b if best_track == track_a else track_a
            cand = cand_b if best_track == track_a else cand_a
            overlaps = cand_a if best_track == track_a else cand_b

            resolutions.append({
                "candidate_title": cand,
                "original_track_name": orig_track,
                "best_fit_track_name": best_track,
                "overlapping_with_title": overlaps,
                "similarity_score": float(d.get("similarity_score", 0.0)),
                "resolution_rationale": d.get("resolution_note", ""),
            })
        return resolutions


class MultiTrackPipelineResult(BaseModel):
    """End-to-end outcome of a multi-track research session."""

    session_id: str
    input: HackathonInput
    shared_intelligence: HackathonIntelligence | None = None
    track_results: dict[str, TrackResult] = Field(default_factory=dict)
    comparison: CrossTrackComparisonResult | None = None
    master_report: FinalReport | None = None
    master_report_path: str | None = None
    status: str = "completed"  # "completed", "completed_no_winner", "failed"
    error: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    duration_seconds: float = 0.0

    def finalize(self) -> None:
        self.completed_at = utc_now()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

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
        if self.comparison:
            has_winner = bool(
                self.comparison.overall_winning_candidate
                or any(w for w in self.comparison.per_track_winners.values() if w)
            )
            return WinnerOutcome.WINNER_SELECTED if has_winner else WinnerOutcome.NO_QUALIFYING_WINNER
        if self.master_report and self.master_report.has_winner:
            return WinnerOutcome.WINNER_SELECTED
        if self.master_report:
            return WinnerOutcome.NO_QUALIFYING_WINNER
        return WinnerOutcome.NOT_EVALUATED
