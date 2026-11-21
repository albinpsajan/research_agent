"""Reconstruct a PipelineResult from persisted agent results."""

from __future__ import annotations

import json
from datetime import datetime

from src.database.repository import Repository
from src.models.candidate import FeasibilityReport
from src.models.domain import DomainMap
from src.models.evaluation import FinalEvaluationReport
from src.models.hackathon import HackathonInput, HackathonIntelligence, HackathonTrack, MultiTrackMode
from src.models.multitrack import (
    CrossTrackComparisonResult,
    MultiTrackPipelineResult,
    TrackResult,
)
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


def load_multi_track_result(
    session_id: str, repository: Repository | None = None
) -> MultiTrackPipelineResult | None:
    """Load a persisted multi-track research session, or None if not found/not multi-track."""
    repository = repository or Repository()
    session = repository.get_session(session_id)
    if not session:
        return None

    tracks_rows = repository.get_tracks(session_id)
    tracks = [
        HackathonTrack(
            id=r["id"],
            name=r["track_name"],
            description=r.get("description") or "",
            track_rules=r.get("track_rules") or "",
            official_track_url=r.get("official_url") or "",
        )
        for r in tracks_rows
    ]

    mode_raw = session.get("multi_track_mode") or "best_overall"
    mode = MultiTrackMode.BEST_PER_TRACK if mode_raw == "best_per_track" else MultiTrackMode.BEST_OVERALL

    deadline = None
    if session.get("deadline"):
        try:
            deadline = datetime.fromisoformat(str(session["deadline"]))
        except ValueError:
            pass

    hackathon = HackathonInput(
        theme=session["hackathon_theme"],
        name=session.get("hackathon_name"),
        website_url=session.get("website_url"),
        rules_url=session.get("rules_url"),
        deadline=deadline,
        constraints=session.get("constraints"),
        session_id=session_id,
        is_multi_track=True,
        multi_track_mode=mode,
        tracks=tracks,
    )

    shared_intelligence = _model(
        HackathonIntelligence, _latest(repository, session_id, "shared_intelligence")
    ) or _model(
        HackathonIntelligence, _latest(repository, session_id, "hackathon_intelligence")
    )

    comp_row = repository.get_multi_track_comparison(session_id)
    comparison = None
    if comp_row and comp_row.get("comparison"):
        try:
            comparison = CrossTrackComparisonResult.model_validate(comp_row["comparison"])
        except Exception:
            comparison = None

    master_report = None
    reports = repository.get_session_reports(session_id)
    for rep in reports:
        try:
            parsed_rep = FinalReport.model_validate(json.loads(rep["report_json"]))
            if "multitrack" in rep.get("id", "") or "multitrack" in parsed_rep.metadata.report_id:
                master_report = parsed_rep
                break
            if not master_report:
                master_report = parsed_rep
        except Exception:
            pass

    # Reconstruct individual track results
    track_results: dict[str, TrackResult] = {}
    for track in tracks:
        track_input = HackathonInput(
            theme=f"{hackathon.theme} — Track: {track.name}",
            name=hackathon.name,
            website_url=track.official_track_url or hackathon.website_url,
            rules_url=hackathon.rules_url,
            deadline=hackathon.deadline,
            constraints=hackathon.constraints,
            session_id=session_id,
        )
        track_results[track.id] = TrackResult(
            track=track,
            input=track_input,
            status="completed",
        )

    res = MultiTrackPipelineResult(
        session_id=session_id,
        input=hackathon,
        shared_intelligence=shared_intelligence,
        track_results=track_results,
        comparison=comparison,
        master_report=master_report,
        master_report_path=f"data/reports/{master_report.metadata.report_id}.md" if master_report else None,
        status=session.get("status", "unknown"),
    )
    if session.get("created_at"):
        try:
            res.started_at = datetime.fromisoformat(str(session["created_at"]))
        except ValueError:
            pass
    res.completed_at = res.started_at
    return res



def _model(model_type, payload: dict | None):
    if not payload:
        return None
    try:
        return model_type.model_validate(payload)
    except ValueError:
        return None
