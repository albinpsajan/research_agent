"""Comprehensive test suite for interrupted research sessions, winner outcome separation,
execution reliability, checkpoint restoration, and safe resumption.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch

from src.database.connection import DatabaseConnection
from src.database.migrations import initialize_database
from src.database.repository import Repository
from src.models.candidate import CandidateSolution, FeasibilityReport
from src.models.domain import DiscoveredDomain, DomainMap, ProblemCandidate
from src.models.evaluation import CandidateEvaluation, FinalEvaluationReport, WinnerSelection
from src.models.hackathon import HackathonInput, HackathonIntelligence, HackathonTrack, MultiTrackMode
from src.models.multitrack import CrossTrackComparisonResult, MultiTrackPipelineResult, TrackResult
from src.models.pipeline import (
    PipelineOptions,
    PipelineResult,
    ResearchExecutionStatus,
    WinnerOutcome,
)
from src.orchestration.background_runner import (
    can_resume_session,
    get_job_status,
    is_job_active,
    resume_research_job,
    start_research_job,
    _JOBS,
    _LOCK,
)
from src.orchestration.loader import load_session_result, load_multi_track_result
from src.orchestration.pipeline import HackathonPipeline


@pytest.fixture
def test_repo(tmp_path):
    db_path = tmp_path / "test_lifecycle.db"
    db = DatabaseConnection(db_path)
    initialize_database(db)
    return Repository(db)


# ---------------------------------------------------------------------------
# 1. Successful research with a winner
# ---------------------------------------------------------------------------
def test_successful_research_with_winner():
    winner_ev = CandidateEvaluation(
        candidate_id="c1",
        candidate_title="Smart Irrigation AI",
        domain="Agriculture",
        total_score=88.5,
        all_gates_passed=True,
        is_qualified=True,
    )
    winner_sel = WinnerSelection(
        has_winner=True,
        winner=winner_ev,
        total_candidates_evaluated=3,
    )
    result = PipelineResult(
        session_id="sess_winner_01",
        input=HackathonInput(theme="Water Tech"),
        winner=winner_sel,
        status="completed",
    )
    assert result.execution_status == ResearchExecutionStatus.COMPLETED
    assert result.winner_outcome == WinnerOutcome.WINNER_SELECTED


# ---------------------------------------------------------------------------
# 2. Successful research with no qualifying winner
# ---------------------------------------------------------------------------
def test_successful_research_with_no_qualifying_winner():
    winner_sel = WinnerSelection(
        has_winner=False,
        winner=None,
        rejection_reason="Failed Gate 5: Unit Economics",
        total_candidates_evaluated=3,
        total_candidates_rejected=3,
    )
    result = PipelineResult(
        session_id="sess_nowinner_01",
        input=HackathonInput(theme="Solar Energy"),
        winner=winner_sel,
        status="completed_no_winner",
    )
    assert result.execution_status == ResearchExecutionStatus.COMPLETED
    assert result.winner_outcome == WinnerOutcome.NO_QUALIFYING_WINNER


# ---------------------------------------------------------------------------
# 3. Interruption during Agent 1
# ---------------------------------------------------------------------------
def test_interruption_during_agent_1():
    result = PipelineResult(
        session_id="sess_interrupted_a1",
        input=HackathonInput(theme="Autonomous Drones"),
        status="interrupted",
        intelligence=None,
        winner=None,
    )
    assert result.execution_status == ResearchExecutionStatus.INTERRUPTED
    assert result.winner_outcome == WinnerOutcome.NOT_EVALUATED
    # MUST NOT be declared as a no-winner session
    assert result.winner_outcome != WinnerOutcome.NO_QUALIFYING_WINNER


# ---------------------------------------------------------------------------
# 4. Interruption during Agent 2
# ---------------------------------------------------------------------------
def test_interruption_during_agent_2(test_repo):
    sid = "sess_interrupted_a2"
    test_repo.create_session(theme="AI Diagnostics", name="AI Healthcare", session_id=sid)
    intel = HackathonIntelligence(
        hackathon_input=HackathonInput(theme="AI Diagnostics"),
        verified_facts=["Global hospital network"],
    )
    test_repo.save_agent_result(sid, "hackathon_intelligence", "hackathon_intelligence", intel.model_dump(mode="json"))
    test_repo.update_session_status(sid, "interrupted")

    loaded = load_session_result(sid, test_repo)
    assert loaded is not None
    assert loaded.execution_status == ResearchExecutionStatus.INTERRUPTED
    assert loaded.winner_outcome == WinnerOutcome.NOT_EVALUATED
    assert loaded.intelligence is not None

    can_res, reason, checkpoints = can_resume_session(sid, test_repo)
    assert can_res is True
    assert "hackathon_intelligence" in checkpoints


# ---------------------------------------------------------------------------
# 5. Interruption during multi-track execution
# ---------------------------------------------------------------------------
def test_interruption_during_multi_track(test_repo):
    sid = "sess_multi_interrupted"
    test_repo.create_session(theme="AI Innovation", name="Hackathon Multi", is_multi_track=True, session_id=sid)
    t1 = HackathonTrack(id="t1", name="Track 1 Fintech")
    t2 = HackathonTrack(id="t2", name="Track 2 Healthtech")
    test_repo.save_tracks(sid, [t1, t2])

    # Track 1 completed, Track 2 failed with an error
    tr1 = TrackResult(track=t1, input=HackathonInput(theme="Fintech"), status="completed")
    tr2 = TrackResult(track=t2, input=HackathonInput(theme="Healthtech"), status="failed", error="Timeout during search")

    comp_result = CrossTrackComparisonResult(
        mode=MultiTrackMode.BEST_OVERALL,
        overall_winning_track=None,
        overall_winning_candidate=None,
    )

    all_failed = all(t.status == "failed" for t in [tr1, tr2])
    any_failed = any(t.status == "failed" for t in [tr1, tr2])
    overall_status = "failed" if all_failed else ("interrupted" if any_failed else "completed_no_winner")

    multi_res = MultiTrackPipelineResult(
        session_id=sid,
        input=HackathonInput(theme="AI Innovation", is_multi_track=True, tracks=[t1, t2]),
        track_results={"t1": tr1, "t2": tr2},
        comparison=comp_result,
        status=overall_status,
    )

    assert multi_res.execution_status == ResearchExecutionStatus.INTERRUPTED
    # Failed track must NOT silently become NO_QUALIFYING_WINNER
    assert multi_res.winner_outcome == WinnerOutcome.NOT_EVALUATED


# ---------------------------------------------------------------------------
# 6. Ollama timeout / error handling
# ---------------------------------------------------------------------------
def test_ollama_timeout_handling(test_repo):
    sid = "sess_ollama_timeout"
    test_repo.create_session(theme="Quantum Cryptography", name="Quantum Computing", session_id=sid)

    # Save pipeline error result as captured on timeout
    test_repo.save_agent_result(
        sid,
        "orchestrator",
        "pipeline_error",
        {
            "stage": "domain_discovery",
            "error": "Ollama connection timed out after 120.0s",
            "error_type": "OllamaTimeoutError",
        },
    )
    test_repo.update_session_status(sid, "failed")

    loaded = load_session_result(sid, test_repo)
    assert loaded is not None
    assert loaded.execution_status == ResearchExecutionStatus.FAILED
    assert loaded.winner_outcome == WinnerOutcome.NOT_EVALUATED
    assert "OllamaTimeoutError" in (loaded.error or "")


# ---------------------------------------------------------------------------
# 7. Application restart during research
# ---------------------------------------------------------------------------
def test_application_restart_during_research(test_repo):
    sid = "sess_restart_orphan"
    test_repo.create_session(theme="Autonomous Traffic", name="Smart Cities", session_id=sid)
    test_repo.update_session_status(sid, "running")

    # Ensure not active in in-memory runner
    with _LOCK:
        _JOBS.pop(sid, None)

    status_data = get_job_status(sid, test_repo)
    assert status_data is not None
    # Auto-healed from 'running' to 'interrupted'
    assert status_data["status"] == "interrupted"
    assert status_data["stage"] == "Interrupted"

    loaded = load_session_result(sid, test_repo)
    assert loaded.execution_status == ResearchExecutionStatus.INTERRUPTED
    assert loaded.winner_outcome == WinnerOutcome.NOT_EVALUATED


# ---------------------------------------------------------------------------
# 8. Streamlit rerun during research (duplicate prevention)
# ---------------------------------------------------------------------------
def test_streamlit_rerun_during_research(test_repo):
    sid = "sess_active_job_01"
    test_repo.create_session(theme="Clean Energy", name="Green Hydrogen", session_id=sid)
    inp = HackathonInput(theme="Clean Energy", session_id=sid)
    opts = PipelineOptions()

    with _LOCK:
        _JOBS[sid] = {
            "session_id": sid,
            "theme": inp.theme,
            "name": "Hackathon",
            "is_multi_track": False,
            "status": "running",
            "stage": "1. Ground Truth",
            "message": "Reading rules...",
            "progress": 0.2,
            "error": None,
        }

    # Second launch call on Streamlit rerun must return False without creating duplicate thread
    launched = start_research_job(sid, inp, opts)
    assert launched is False
    assert is_job_active(sid) is True

    # Cleanup
    with _LOCK:
        _JOBS.pop(sid, None)


# ---------------------------------------------------------------------------
# 9. Resume from a persisted checkpoint
# ---------------------------------------------------------------------------
def test_resume_from_persisted_checkpoint(test_repo):
    sid = "sess_resume_chk"
    test_repo.create_session(theme="Personalized Learning", name="EdTech Platform", session_id=sid)

    # Persist Agent 1 and Agent 2 checkpoints
    intel = HackathonIntelligence(
        hackathon_input=HackathonInput(theme="Personalized Learning"),
        verified_facts=["Target: K-12 students"],
    )
    test_repo.save_agent_result(sid, "hackathon_intelligence", "hackathon_intelligence", intel.model_dump(mode="json"))

    dmap = DomainMap(
        theme="Personalized Learning",
        domains=[DiscoveredDomain(name="Adaptive Testing", description="Testing", relevance_type="primary", relevance_explanation="Core")],
        problem_candidates=[ProblemCandidate(id="P01", title="Static Question Banks", description="Questions are repetitive and lack adaptiveness", domain="Adaptive Testing")],
        total_domains_explored=1,
        total_problems_found=1,
    )
    test_repo.save_agent_result(sid, "domain_discovery", "domain_map", dmap.model_dump(mode="json"))

    mock_llm = MagicMock()
    pipeline = HackathonPipeline(llm=mock_llm, repository=test_repo)

    # Mock the agents: HackathonIntelligenceAgent & DomainDiscoveryAgent should NOT be called
    with patch("src.orchestration.pipeline.HackathonIntelligenceAgent") as mock_a1, \
         patch("src.orchestration.pipeline.DomainDiscoveryAgent") as mock_a2, \
         patch("src.orchestration.pipeline.InnovationResearchAgent") as mock_a3, \
         patch("src.orchestration.pipeline.SolutionArchitectAgent") as mock_a4, \
         patch("src.orchestration.pipeline.AdversarialCriticAgent") as mock_a5:

        mock_a3.return_value.run.return_value = MagicMock(total_solutions_found=2, gaps=[])
        mock_a4.return_value.run.return_value = MagicMock(candidates=[])
        mock_a5.return_value.run.return_value = MagicMock(
            evaluations=[],
            debates=[],
            winner=WinnerSelection(has_winner=False, rejection_reason="No candidates"),
        )

        inp = HackathonInput(theme="Personalized Learning", session_id=sid)
        res = pipeline.run(inp, session_id=sid, resume=True)

        # Agent 1 and Agent 2 were skipped because checkpoints existed
        mock_a1.assert_not_called()
        mock_a2.assert_not_called()
        # Agent 3 ran
        mock_a3.assert_called_once()


# ---------------------------------------------------------------------------
# 10. Duplicate resume prevention
# ---------------------------------------------------------------------------
def test_duplicate_resume_prevention(test_repo):
    sid = "sess_dup_resume"
    test_repo.create_session(theme="Microloans", name="Fintech", session_id=sid)
    test_repo.update_session_status(sid, "interrupted")

    with _LOCK:
        _JOBS[sid] = {"status": "running"}

    can_res, reason, _ = can_resume_session(sid, test_repo)
    assert can_res is False
    assert "currently active" in reason

    launched = resume_research_job(sid, test_repo)
    assert launched is False

    with _LOCK:
        _JOBS.pop(sid, None)


# ---------------------------------------------------------------------------
# 11. Partial result preservation
# ---------------------------------------------------------------------------
def test_partial_result_preservation(test_repo):
    sid = "sess_partial_pres"
    test_repo.create_session(theme="Precision Farming", name="AgriTech", session_id=sid)

    # Save domain map and problem candidates
    dmap = DomainMap(
        theme="Precision Farming",
        domains=[DiscoveredDomain(name="Soil Sensing", description="Sensors", relevance_type="primary", relevance_explanation="Direct")],
        problem_candidates=[ProblemCandidate(id="P01", title="Low Moisture Warning", description="Sensors fail to trigger alerts on sudden drought", domain="Soil Sensing")],
        total_domains_explored=1,
        total_problems_found=1,
    )
    test_repo.save_agent_result(sid, "domain_discovery", "domain_map", dmap.model_dump(mode="json"))
    test_repo.update_session_status(sid, "interrupted")

    # Load session
    loaded = load_session_result(sid, test_repo)
    assert loaded is not None
    assert loaded.domain_map is not None
    assert loaded.domain_map.total_domains_explored == 1
    assert loaded.domain_map.total_problems_found == 1
    assert loaded.domain_map.problem_candidates[0].title == "Low Moisture Warning"


# ---------------------------------------------------------------------------
# 12. Correct History and Results status for session 027be314
# ---------------------------------------------------------------------------
def test_session_027be314_history_and_results_status():
    real_repo = Repository()
    sid = "027be314-9d61-4316-b10c-cf2f1f8d7846"
    session_row = real_repo.get_session(sid)
    if not session_row:
        pytest.skip("Session 027be314 not present in current hackathoniq.db")

    loaded = load_session_result(sid, real_repo)
    assert loaded is not None
    assert loaded.session_id.startswith("027be314")
    assert loaded.execution_status == ResearchExecutionStatus.INTERRUPTED
    assert loaded.winner_outcome == WinnerOutcome.NOT_EVALUATED
    # MUST NOT say no qualifying winner
    assert loaded.winner_outcome != WinnerOutcome.NO_QUALIFYING_WINNER
    assert loaded.winner is None

    can_res, reason, checkpoints = can_resume_session(sid, real_repo)
    assert can_res is True
    assert "hackathon_intelligence" in checkpoints
    assert "domain_discovery" in checkpoints


# ---------------------------------------------------------------------------
# 13. Database compatibility with historical sessions
# ---------------------------------------------------------------------------
def test_database_compatibility_with_historical_sessions():
    real_repo = Repository()
    sessions = real_repo.list_sessions(limit=50)
    for s in sessions:
        sid = s["id"]
        res = load_session_result(sid, real_repo)
        if res:
            # Check that every historical session cleanly maps to valid enums
            assert isinstance(res.execution_status, ResearchExecutionStatus)
            assert isinstance(res.winner_outcome, WinnerOutcome)
            if res.execution_status == ResearchExecutionStatus.INTERRUPTED:
                assert res.winner_outcome == WinnerOutcome.NOT_EVALUATED
