"""Integration tests for the full LangGraph workflow (offline fakes)."""

from __future__ import annotations

from pathlib import Path

import pytest

from config.settings import get_settings
from src.models.hackathon import HackathonInput
from src.models.pipeline import PipelineOptions
from src.orchestration.pipeline import HackathonPipeline
from tests.fakes import FakeIntelligence, FakeLLM, FakeResearch


class FailingLLM(FakeLLM):
    def generate_json(self, prompt, schema, system=None, temperature=None):
        if schema.__name__ == "DomainListLLM":
            raise RuntimeError("simulated model failure")
        return super().generate_json(prompt, schema, system, temperature)


@pytest.fixture()
def report_dir(tmp_path: Path, monkeypatch):
    settings = get_settings()
    target = tmp_path / "reports"
    monkeypatch.setattr(settings.storage, "reports_dir", target)
    return target


def _pipeline(repository, llm, research) -> HackathonPipeline:
    return HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )


def test_full_workflow_selects_one_winner(repository, report_dir: Path) -> None:
    llm = FakeLLM(score=8.0)
    research = FakeResearch()
    events: list[tuple[str, float]] = []
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
        progress=lambda stage, message, fraction: events.append((stage, fraction)),
    )
    result = pipeline.run(
        HackathonInput(theme="Sustainable cities", name="CityHack"),
        PipelineOptions(max_domains=5, problems_per_domain=2, max_finalists=4),
    )

    assert result.status == "completed", result.error
    assert result.error is None
    assert result.domain_map is not None
    assert result.domain_map.total_domains_explored == 3
    assert result.domain_map.total_problems_found == 3
    assert len({p.domain for p in result.domain_map.problem_candidates}) >= 2
    assert result.innovation_report is not None
    assert result.feasibility is not None
    assert result.feasibility.candidates
    assert result.winner is not None and result.winner.has_winner
    assert result.winner.winner is not None
    assert result.winner.winner.total_score == 80.0
    assert result.winner.winner.all_gates_passed
    assert result.debates and result.debates[0].rounds
    assert result.report is not None
    assert len(result.report.sections) == 24
    assert "Exposure-aware" in result.report.sections[10].content
    assert result.report.evidence_links
    assert (report_dir / f"{result.report.metadata.report_id}.md").exists()

    session = repository.get_session(result.session_id)
    assert session is not None and session["status"] == "completed"
    assert repository.get_agent_results(result.session_id)
    assert repository.get_session_reports(result.session_id)
    assert repository.get_evaluations(result.session_id)
    assert repository.get_debate_history(result.session_id)
    assert events[0][0] == "prepare"
    assert events[-1][1] == 1.0
    assert "ProblemListLLM" in llm.calls
    assert "SelectionLLM" in llm.calls


def test_workflow_can_reject_every_candidate(repository, report_dir: Path) -> None:
    result = _pipeline(repository, FakeLLM(force_reject_all=True), FakeResearch()).run(
        HackathonInput(theme="Sustainable cities"),
        PipelineOptions(max_domains=4, max_finalists=3),
    )
    assert result.status == "completed_no_winner"
    assert result.winner is not None
    assert not result.winner.has_winner
    assert "rejected" in (result.winner.rejection_reason or "").lower()
    assert result.report is not None
    assert len(result.report.sections) == 24
    assert "No winner" in result.report.sections[10].content


def test_workflow_reports_failure_and_preserves_session(
    repository, report_dir: Path
) -> None:
    result = _pipeline(repository, FailingLLM(), FakeResearch()).run(
        HackathonInput(theme="Sustainable cities"),
        PipelineOptions(max_domains=4),
    )
    assert result.status == "failed"
    assert "simulated model failure" in (result.error or "")
    session = repository.get_session(result.session_id)
    assert session is not None and session["status"] == "failed"
    error_results = repository.get_agent_results(result.session_id, "orchestrator")
    assert any(row["result_type"] == "pipeline_error" for row in error_results)
