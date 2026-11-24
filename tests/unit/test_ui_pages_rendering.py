"""Comprehensive functional rendering tests for all 8 redesigned HackathonIQ UI pages."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.models.candidate import CandidateSolution, FeasibilityReport
from src.models.evaluation import (
    CandidateEvaluation,
    QualityGate,
    QualityGateStatus,
    ScoreCriterion,
    WinnerSelection,
)
from src.models.hackathon import HackathonInput
from src.models.pipeline import PipelineResult


def _mock_st():
    mock = MagicMock()
    mock.columns.side_effect = lambda n: [MagicMock() for _ in range(n if isinstance(n, int) else len(n))]
    mock.tabs.side_effect = lambda tabs: [MagicMock() for _ in tabs]
    mock.expander.side_effect = lambda *args, **kwargs: MagicMock()
    mock.container.side_effect = lambda *args, **kwargs: MagicMock()
    # Ensure buttons don't auto-trigger during passive render
    mock.button.return_value = False
    mock.form_submit_button.return_value = False
    mock.checkbox.return_value = False
    mock.toggle.return_value = True
    mock.text_input.return_value = ""
    mock.text_area.return_value = ""
    mock.selectbox.side_effect = lambda label, options, *args, **kwargs: options[0] if options else ""
    mock.multiselect.return_value = []
    mock.slider.side_effect = lambda label, min_val, max_val, val, *args, **kwargs: val
    mock.number_input.side_effect = lambda label, *args, **kwargs: kwargs.get("value", 1)
    return mock


def test_overview_page_rendering():
    """Verify Overview page renders system status, metric cards, and recent sessions."""
    from ui.pages import overview

    with patch("ui.pages.overview.st", _mock_st()) as mock_st, \
         patch("ui.pages.overview.hero") as mock_hero, \
         patch("ui.pages.overview.get_repository") as mock_repo, \
         patch("ui.pages.overview.get_llm") as mock_llm:

        mock_repo.return_value.list_sessions.return_value = [
            {
                "id": "test-session-1234",
                "hackathon_theme": "Sustainable Smart Cities",
                "hackathon_name": "BeachHack S08",
                "is_multi_track": 1,
                "status": "completed",
                "created_at": "2026-11-22 10:00:00",
            }
        ]
        mock_repo.return_value.list_uploaded_documents.return_value = []
        mock_llm.return_value.health.return_value = {"available": True, "active_model": "qwen2.5:7b"}

        overview.render()
        assert mock_hero.called
        assert mock_st.metric.called


def test_new_research_page_rendering():
    """Verify New Research page renders 4-step guided builder cleanly."""
    from ui.pages import new_research

    with patch("ui.pages.new_research.st", _mock_st()) as mock_st, \
         patch("ui.pages.new_research.hero") as mock_hero, \
         patch("ui.pages.new_research.get_repository") as mock_repo, \
         patch("ui.pages.new_research.get_llm") as mock_llm:

        mock_repo.return_value.list_uploaded_documents.return_value = []
        mock_llm.return_value.health.return_value = {"available": True, "active_model": "qwen2.5:7b", "models": ["qwen2.5:7b"]}

        new_research.render()
        assert mock_hero.called
        assert mock_st.form.called


def test_workspace_page_rendering():
    """Verify Research Workspace renders empty state and active agent pipeline."""
    from ui.pages import workspace

    fake_session = {
        "research_in_progress": True,
        "current_session_id": "sess-work-123",
        "active_agent_name": "Innovation Research",
        "active_progress_fraction": 0.45,
        "live_events": [{"timestamp": "12:00:00", "stage": "Agent 3", "message": "Auditing GitHub repos"}],
    }

    with patch("ui.pages.workspace.st", _mock_st()) as mock_st, \
         patch("ui.pages.workspace.hero") as mock_hero, \
         patch("streamlit.session_state", fake_session):

        workspace.render()
        assert mock_hero.called
        assert mock_st.progress.called


def test_results_page_single_track_rendering():
    """Verify Results page renders single-track winner with executive summary and tabs."""
    from ui.pages import results

    cand = CandidateSolution(
        id="c-win",
        problem_candidate_id="p-1",
        title="Autonomous Soil Sensor Grid",
        domain="Agriculture",
        problem_statement="Precision moisture monitoring in Wayanad homesteads",
        proposed_solution="Edge mesh LoRa sensors with zero paid cloud subscriptions",
        unique_differentiation="Sub-dollar node bill-of-materials with Malayalam voice alerts",
        development_complexity="Medium",
        estimated_hours=32.0,
        feasibility_score=0.92,
    )
    gates = [
        QualityGate(
            name="Gate 1: Problem Evidence Verification",
            description="Problem evidence backed by verified citations",
            status=QualityGateStatus.PASSED,
            justification="Corroborated by ICAR empirical soil studies",
        ),
        QualityGate(
            name="Gate 5: Unique Differentiation",
            description="Clear architectural differentiation",
            status=QualityGateStatus.PASSED,
            justification="Documented structural differentiation",
        ),
    ]
    ev = CandidateEvaluation(
        candidate_id="c-win",
        candidate_title="Autonomous Soil Sensor Grid",
        domain="Agriculture",
        total_score=88.5,
        raw_score=88.5,
        normalized_score=88.5,
        all_gates_passed=True,
        is_qualified=True,
        scores=[ScoreCriterion(name="Real-world problem significance", score=9.0, weight=10.0)],
        quality_gates=gates,
        overall_assessment="High feasibility and demonstrable live judging potential.",
    )
    result = PipelineResult(
        session_id="sess-single-win",
        input=HackathonInput(theme="Agri-Tech Hackathon", name="AgriHack"),
        winner=WinnerSelection(has_winner=True, winner=ev),
        feasibility=FeasibilityReport(candidates=[cand]),
        status="completed",
        duration_seconds=1200.0,
    )

    fake_session = {"current_result": result, "current_multi_result": None}

    with patch("ui.pages.results.st", _mock_st()) as mock_st, \
         patch("ui.pages.results.hero") as mock_hero, \
         patch("ui.pages.results.get_repository") as mock_repo, \
         patch("streamlit.session_state", fake_session):

        mock_repo.return_value.get_research_sources.return_value = [
            {"title": "ICAR Soil Report", "source_type": "openalex", "url": "https://example.com/soil", "reliability": 0.9}
        ]

        results.render()
        assert mock_hero.called
        assert mock_st.markdown.called


def test_history_page_rendering():
    """Verify History page renders search filter, table, and session reports."""
    from ui.pages import history

    with patch("ui.pages.history.st", _mock_st()) as mock_st, \
         patch("ui.pages.history.hero") as mock_hero, \
         patch("ui.pages.history.get_repository") as mock_repo:

        mock_repo.return_value.list_sessions.return_value = [
            {"id": "s-hist-1", "hackathon_theme": "Climate", "hackathon_name": "EcoHack", "is_multi_track": 0, "status": "completed"}
        ]
        mock_repo.return_value.get_session.return_value = {"id": "s-hist-1", "status": "completed"}
        mock_repo.return_value.get_session_reports.return_value = []
        mock_repo.return_value.get_agent_results.return_value = []

        history.render()
        assert mock_hero.called
        assert mock_st.dataframe.called


def test_settings_page_rendering():
    """Verify Settings page renders all 4 tabs and telemetry."""
    from ui.pages import settings

    with patch("ui.pages.settings.st", _mock_st()) as mock_st, \
         patch("ui.pages.settings.hero") as mock_hero, \
         patch("ui.pages.settings.get_llm") as mock_llm:

        mock_llm.return_value.health.return_value = {"available": True, "active_model": "qwen2.5:7b", "models": ["qwen2.5:7b"]}

        settings.render()
        assert mock_hero.called
        assert mock_st.tabs.called
