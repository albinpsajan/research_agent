"""Background research orchestration manager.

Executes autonomous research pipelines in non-blocking background threads,
ensuring Streamlit UI navigation remains fluid while agents deliberate.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from config.logging_config import get_logger
from src.database.repository import Repository
from src.llm.client import OllamaClient
from src.models.hackathon import HackathonInput
from src.models.pipeline import PipelineOptions
from src.orchestration.pipeline import HackathonPipeline

logger = get_logger("orchestration.background")

_LOCK = threading.Lock()
# Active or recent jobs: session_id -> dict
_JOBS: dict[str, dict[str, Any]] = {}


def start_research_job(
    session_id: str,
    hackathon: HackathonInput,
    options: PipelineOptions,
) -> bool:
    """Start an isolated research execution in a background thread.
    
    Returns True if launched, or False if already running.
    """
    with _LOCK:
        job = _JOBS.get(session_id)
        if job and job.get("status") == "running":
            logger.warning("Research job already running for session %s", session_id[:8])
            return False

        _JOBS[session_id] = {
            "session_id": session_id,
            "theme": hackathon.theme,
            "name": hackathon.name or "Hackathon",
            "is_multi_track": hackathon.is_multi_track,
            "status": "running",
            "stage": "1. Ground Truth & Rules Analysis",
            "message": "Initializing autonomous agents and reading constraints...",
            "progress": 0.05,
            "error": None,
            "started_at": datetime.now(),
            "completed_at": None,
        }

    thread = threading.Thread(
        target=_research_worker,
        args=(session_id, hackathon, options),
        daemon=True,
        name=f"research-{session_id[:8]}",
    )
    thread.start()
    logger.info("Launched background research thread for session %s", session_id[:8])
    return True


def _research_worker(
    session_id: str,
    hackathon: HackathonInput,
    options: PipelineOptions,
) -> None:
    """Thread worker: instantiates independent DB and LLM clients."""
    repo = Repository()
    llm = OllamaClient()

    stage_names = {
        "intelligence": "1. Ground Truth & Rules Analysis",
        "domain": "2. Dynamic Domain & Problem Discovery",
        "innovation": "3. Competitor Investigation & Benchmarking",
        "architect": "4. Solution Architecture & Feasibility",
        "critic": "5. Quality Gate Evaluation & Debate",
    }

    def on_progress(stage: str, message: str, frac: float) -> None:
        frac_bounded = min(max(frac, 0.0), 1.0)
        clean_stage = stage_names.get(stage.lower(), stage)
        with _LOCK:
            if session_id in _JOBS:
                _JOBS[session_id]["stage"] = clean_stage
                _JOBS[session_id]["message"] = message
                _JOBS[session_id]["progress"] = frac_bounded
                _JOBS[session_id]["updated_at"] = datetime.now()

    pipeline = HackathonPipeline(llm=llm, repository=repo, progress=on_progress)
    repo.update_session_status(session_id, "running")

    try:
        logger.info("Background execution running for session %s", session_id[:8])
        if hackathon.is_multi_track:
            pipeline.run_multi_track(hackathon, options, session_id=session_id)
        else:
            pipeline.run(hackathon, options, session_id=session_id)

        with _LOCK:
            if session_id in _JOBS:
                _JOBS[session_id]["status"] = "completed"
                _JOBS[session_id]["progress"] = 1.0
                _JOBS[session_id]["stage"] = "Research Completed"
                _JOBS[session_id]["message"] = "Solution blueprints, gate audits, and reports finalized."
                _JOBS[session_id]["completed_at"] = datetime.now()

        logger.info("Background execution successfully finished for session %s", session_id[:8])

    except Exception as exc:  # noqa: BLE001
        logger.error("Background research failed for session %s: %s", session_id[:8], exc, exc_info=True)
        repo.update_session_status(session_id, "failed")
        with _LOCK:
            if session_id in _JOBS:
                _JOBS[session_id]["status"] = "failed"
                _JOBS[session_id]["error"] = str(exc)
                _JOBS[session_id]["stage"] = "Execution Failed"
                _JOBS[session_id]["message"] = f"Failed: {exc}"
                _JOBS[session_id]["completed_at"] = datetime.now()


def get_job_status(session_id: str, repository: Repository | None = None) -> dict[str, Any] | None:
    """Retrieve in-memory or database status for a session."""
    with _LOCK:
        job = _JOBS.get(session_id)
        if job:
            return dict(job)

    # Fall back to repository status
    repo = repository or Repository()
    session = repo.get_session(session_id)
    if not session:
        return None

    db_status = session.get("status") or "created"
    # Auto-heal orphaned sessions from previous server runs
    if db_status in ("running", "in_progress", "started"):
        reports = repo.get_session_reports(session_id)
        if reports:
            db_status = "completed"
        else:
            db_status = "interrupted"
        try:
            repo.update_session_status(session_id, db_status)
        except Exception:
            pass

    return {
        "session_id": session_id,
        "theme": session.get("hackathon_theme") or "",
        "name": session.get("hackathon_name") or "Hackathon",
        "is_multi_track": bool(session.get("is_multi_track")),
        "status": db_status,
        "stage": "Completed" if db_status == "completed" else ("Interrupted" if db_status == "interrupted" else "Idle"),
        "message": "" if db_status != "interrupted" else "Session interrupted during previous run",
        "progress": 1.0 if db_status == "completed" else 0.0,
        "error": None,
    }


def is_job_active(session_id: str) -> bool:
    """Check if a session is actively running in background."""
    with _LOCK:
        job = _JOBS.get(session_id)
        return bool(job and job.get("status") == "running")


def list_active_jobs() -> dict[str, dict[str, Any]]:
    """Return all currently active in-memory research jobs."""
    with _LOCK:
        return {
            sid: dict(info)
            for sid, info in _JOBS.items()
            if info.get("status") == "running"
        }
