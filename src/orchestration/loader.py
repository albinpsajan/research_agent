"""Reconstruct a PipelineResult from persisted agent results."""

from __future__ import annotations

import json
from datetime import datetime

from src.database.repository import Repository
from src.models.candidate import FeasibilityReport
from src.models.domain import DomainMap
from src.models.evaluation import FinalEvaluationReport
from src.models.hackathon import HackathonInput, HackathonIntelligence
from src.models.pipeline import PipelineResult
from src.models.report import FinalReport
from src.models.research import InnovationReport


def _latest(repository: Repository, session_id: str, agent: str) -> dict | None:
    result = repository.get_latest_agent_result(session_id, agent)
    return result.get("result_data") if result else None


def load_session_result(
    session_id: str, repository: Repository | None = None
) -> PipelineResult | None:
    """Load a persisted run, returning ``None`` if the session is unknown."""
    repository = repository or Repository()
    session = repository.get_session(session_id)
    if not session:
        return None
    deadline = None
    if session.get("deadline"):
        try:
            deadline = datetime.fromisoformat(str(session["deadline"]))
        except ValueError:
            deadline = None
    hackathon = HackathonInput(
        theme=session["hackathon_theme"],
        name=session.get("hackathon_name"),
        website_url=session.get("website_url"),
        rules_url=session.get("rules_url"),
        deadline=deadline,
        constraints=session.get("constraints"),
        session_id=session_id,
    )
    intelligence = _model(
        HackathonIntelligence, _latest(repository, session_id, "hackathon_intelligence")
    )
    domain_map = _model(DomainMap, _latest(repository, session_id, "domain_discovery"))
    innovation = _model(
        InnovationReport, _latest(repository, session_id, "innovation_research")
    )
    feasibility = _model(
        FeasibilityReport, _latest(repository, session_id, "solution_architect")
    )
    final = _model(
        FinalEvaluationReport, _latest(repository, session_id, "adversarial_critic")
    )
    report = None
    reports = repository.get_session_reports(session_id)
    if reports:
        try:
            report = FinalReport.model_validate(json.loads(reports[0]["report_json"]))
        except (json.JSONDecodeError, ValueError):
            report = None

    result = PipelineResult(
        session_id=session_id,
        input=hackathon,
        intelligence=intelligence,
        domain_map=domain_map,
        innovation_report=innovation,
        feasibility=feasibility,
        debates=final.debates if final else [],
        winner=final.winner if final else None,
        report=report,
        status=session.get("status", "unknown"),
    )
    if session.get("created_at"):
        try:
            result.started_at = datetime.fromisoformat(str(session["created_at"]))
        except ValueError:
            pass
    result.completed_at = result.started_at
    return result


def _model(model_type, payload: dict | None):
    if not payload:
        return None
    try:
        return model_type.model_validate(payload)
    except ValueError:
        return None
