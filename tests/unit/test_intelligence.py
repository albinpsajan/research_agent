"""Continuous Intelligence scheduling and failure-reporting tests."""

from __future__ import annotations

import pytest

from src.database.repository import Repository
from src.intelligence.service import ContinuousIntelligenceService
from src.research.base import ResearchError


class FailingConnector:
    def search(self, query: str, limit: int = 8):
        raise ResearchError("simulated source outage")


def test_refresh_marks_a_total_source_failure(repository: Repository) -> None:
    service = ContinuousIntelligenceService(repository)
    service.sources = {"github_topics": ["climate-tech"]}
    service.github = FailingConnector()
    with pytest.raises(ResearchError):
        service._collect_github()


def test_not_due_refresh_does_no_network_work(repository: Repository) -> None:
    service = ContinuousIntelligenceService(repository)
    repository.log_refresh("github", 1, 1, "success")
    summary = service.run_if_due()
    assert summary.skipped
    assert "Not due" in (summary.skip_reason or "")


def test_theme_lookup_is_honest_when_empty(repository: Repository) -> None:
    service = ContinuousIntelligenceService(repository)
    context = service.context_for_theme("quantum computing")
    assert context.items == []
    assert "No relevant stored intelligence" in context.note
