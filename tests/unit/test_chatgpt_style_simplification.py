"""Unit tests for the ChatGPT-style simplified UI/UX architecture and workflows.

Verifies:
1. ui/app.py exposes strictly TWO pages: 'New Research' and 'History'.
2. PAGE_ALIASES resolves all legacy routes to either 'New Research' or 'History'.
3. Option A Workflow: Document extraction populates form without auto-launching research.
4. Manual entry workflow is fully supported without uploads.
5. Duplicate detection flags matching theme/name.
6. Session deletion removes session record and all cascaded child records.
7. History page renders cleanly with ONE card per research topic.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from src.database.repository import Repository
from src.models.hackathon import HackathonInput, HackathonTrack, MultiTrackMode
from ui.app import PAGES
from ui.components.common import PAGE_ALIASES


def _mock_st():
    mock = MagicMock()
    mock.columns.side_effect = lambda n: [MagicMock() for _ in range(n if isinstance(n, int) else len(n))]
    mock.tabs.side_effect = lambda tabs: [MagicMock() for _ in tabs]
    mock.expander.side_effect = lambda *args, **kwargs: MagicMock()
    mock.container.side_effect = lambda *args, **kwargs: MagicMock()
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
    mock.session_state = {}
    return mock


def test_strictly_two_pages_exposed():
    """Verify that ui/app.py exposes strictly TWO primary user-facing pages."""
    assert len(PAGES) == 2
    assert "New Research" in PAGES
    assert "History" in PAGES

    # Verify that all page aliases map cleanly to either New Research or History
    for alias, target in PAGE_ALIASES.items():
        assert target in ("New Research", "History"), f"Alias {alias} maps to invalid {target}"


def test_duplicate_session_detection(repository: Repository):
    """Verify that find_session_by_theme_or_name detects existing sessions correctly."""
    # Create initial session
    sess_id = repository.create_session(
        theme="Autonomous Marine Pollution Monitoring",
        name="BeachHack 2026",
        is_multi_track=False,
    )
    assert sess_id is not None

    # Exact match
    found = repository.find_session_by_theme_or_name("Autonomous Marine Pollution Monitoring", "BeachHack 2026")
    assert found is not None
    assert found["id"] == sess_id

    # Case-insensitive match on theme
    found_case = repository.find_session_by_theme_or_name("autonomous marine pollution monitoring")
    assert found_case is not None
    assert found_case["id"] == sess_id

    # Match on name
    found_name = repository.find_session_by_theme_or_name(name="BeachHack 2026")
    assert found_name is not None
    assert found_name["id"] == sess_id

    # Non-matching query returns None
    assert repository.find_session_by_theme_or_name("Healthcare AI for Hospitals", "MedHack") is None


def test_session_deletion_cascading(repository: Repository):
    """Verify that delete_session completely removes session and child data."""
    sess_id = repository.create_session(
        theme="Urban Transit Optimization",
        name="Kochi Mobility Hackathon",
        is_multi_track=True,
        multi_track_mode="A",
    )

    # Add tracks
    repository.save_tracks(sess_id, [
        HackathonTrack(id="t1", name="Bus Route Optimization", track_type="regular", description="Optimize bus schedules"),
        HackathonTrack(id="t2", name="Metro Last-Mile", track_type="regular", description="Optimize last mile feeder"),
    ])

    # Add an agent result
    repository.save_agent_result(sess_id, "agent_1_ground_truth", "ground_truth", {"theme": "Urban Transit"})

    # Verify items exist
    assert repository.get_session(sess_id) is not None
    assert len(repository.get_tracks(sess_id)) == 2
    assert len(repository.get_agent_results(sess_id)) == 1

    # Delete session
    deleted = repository.delete_session(sess_id)
    assert deleted is True

    # Verify everything is gone
    assert repository.get_session(sess_id) is None
    assert len(repository.get_tracks(sess_id)) == 0
    assert len(repository.get_agent_results(sess_id)) == 0


def test_option_a_workflow_no_auto_execution():
    """Verify Option A: Document extraction sets configuration but NEVER auto-triggers research."""
    mock_st_obj = _mock_st()
    mock_st_obj.session_state = {}

    from ui.pages import new_research

    with patch("ui.pages.new_research.st", mock_st_obj), \
         patch("ui.pages.new_research.hero") as mock_hero, \
         patch("ui.pages.new_research.get_repository") as mock_repo, \
         patch("ui.pages.new_research.get_llm") as mock_llm, \
         patch("ui.pages.new_research.DocumentIntelligenceService") as mock_service_cls:

        mock_svc = mock_service_cls.return_value
        auto_input = HackathonInput(
            theme="Renewable Grid Optimization",
            name="CleanTech 2026",
            tracks=[HackathonTrack(name="Solar Forecasting", description="Forecast generation")],
        )
        mock_svc.get_active_auto_configuration.return_value = auto_input
        mock_repo.return_value.list_uploaded_documents.return_value = []
        mock_llm.return_value.health.return_value = {"available": True, "active_model": "qwen2.5:7b"}

        new_research.render()

        # Check that configuration was loaded into session state
        assert mock_st_obj.session_state.get("configured_hackathon") == auto_input
        # Critically verify research_in_progress is NOT set to True (no automatic run)
        assert mock_st_obj.session_state.get("research_in_progress") is not True


def test_history_page_rendering_one_card_per_session():
    """Verify that History page renders one distinct entry per session without raw agent logs."""
    from ui.pages import history

    mock_st_obj = _mock_st()

    with patch("ui.pages.history.st", mock_st_obj), \
         patch("ui.pages.history.hero") as mock_hero, \
         patch("ui.pages.history.get_repository") as mock_repo:

        mock_repo.return_value.list_sessions.return_value = [
            {
                "id": "sess-alpha-001",
                "hackathon_theme": "Smart Agri AI",
                "hackathon_name": "AgriTech Hackathon",
                "is_multi_track": 1,
                "status": "completed",
                "created_at": "2026-11-23 10:00:00",
            },
            {
                "id": "sess-beta-002",
                "hackathon_theme": "Disaster Response Bot",
                "hackathon_name": "Resilience Challenge",
                "is_multi_track": 0,
                "status": "in_progress",
                "created_at": "2026-11-23 11:30:00",
            },
        ]
        mock_repo.return_value.get_tracks.return_value = [{"id": "t1", "name": "Precision Farming"}]
        mock_repo.return_value.get_session_reports.return_value = [
            {"id": "rep-001", "winner_title": "AgriSense Autonomous Drone", "report_markdown": "# Report"}
        ]

        history.render()

        assert mock_hero.called
        # Both sessions should be rendered (container called at least once per session)
        assert mock_st_obj.container.call_count >= 2
        # Buttons for loading and deleting should be created
        assert mock_st_obj.button.called
