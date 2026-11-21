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
