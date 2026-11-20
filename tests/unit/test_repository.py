"""Database persistence and de-duplication tests."""

from __future__ import annotations

from src.database.repository import Repository


def test_session_and_agent_results(repository: Repository) -> None:
    session_id = repository.create_session("Test theme", name="Test Hack")
    session = repository.get_session(session_id)
    assert session is not None
    assert session["hackathon_theme"] == "Test theme"
    repository.update_session_status(session_id, "completed")
    assert repository.get_session(session_id)["status"] == "completed"

    repository.save_agent_result(session_id, "agent", "type", {"value": 1})
    results = repository.get_agent_results(session_id, "agent")
    assert results[0]["result_data"] == {"value": 1}
    latest = repository.get_latest_agent_result(session_id, "agent")
    assert latest["result_data"] == {"value": 1}


def test_research_sources_are_deduplicated(repository: Repository) -> None:
    session_id = repository.create_session("Theme")
    first = repository.save_research_source(
        session_id, "https://example.org/a", "A", "web"
    )
    second = repository.save_research_source(
        session_id, "https://example.org/a", "A again", "web"
    )
    assert first == second
    assert len(repository.get_research_sources(session_id)) == 1


def test_intelligence_items_deduplicate_by_url(repository: Repository) -> None:
    first = repository.save_intelligence_item(
        "github", "repository", "Repo", url="https://github.com/a/b"
    )
    second = repository.save_intelligence_item(
        "github", "repository", "Repo duplicate", url="https://github.com/a/b"
    )
    assert first is not None
    assert second is None
    assert repository.intelligence_item_count() == 1
    items = repository.list_intelligence_items()
    assert items[0]["title"] == "Repo"


def test_refresh_log_and_last_refresh(repository: Repository) -> None:
    repository.log_refresh("github", 10, 3, "success")
    last = repository.get_last_refresh()
    assert last is not None
    assert last["items_found"] == 10


def test_report_roundtrip(repository: Repository) -> None:
    session_id = repository.create_session("Theme")
    report_id = repository.save_report(
        session_id, '{"x": 1}', "# Report", True, "Winner"
    )
    assert report_id
    assert repository.get_report(report_id)["winner_title"] == "Winner"
    assert len(repository.get_session_reports(session_id)) == 1
