"""LangGraph state for the five-agent research workflow."""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from src.models.candidate import FeasibilityReport
from src.models.domain import DomainMap
from src.models.evaluation import FinalEvaluationReport
from src.models.hackathon import HackathonInput, HackathonIntelligence
from src.models.pipeline import PipelineOptions
from src.models.report import FinalReport
from src.models.research import InnovationReport


class PipelineState(TypedDict, total=False):
    """Shared state passed between LangGraph nodes."""

    session_id: str
    hackathon: HackathonInput
    options: PipelineOptions
    started_at: datetime
    intelligence_context: str
    continuous_intelligence_note: str
    intelligence: HackathonIntelligence
    domain_map: DomainMap
    innovation_report: InnovationReport
    feasibility: FeasibilityReport
    final_evaluation: FinalEvaluationReport
    report: FinalReport
