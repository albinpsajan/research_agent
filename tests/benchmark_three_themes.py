"""Comprehensive 3-Theme Deterministic Pipeline Validation Benchmark.

Validates HackathonIQ across 3 diverse, real-world representative domains:
1. Agriculture & Climate: "Climate-Resilient Agriculture and Rural Communities"
2. Healthcare & Epidemiology: "AI for Rural Telemedicine and Dengue Outbreak Surveillance"
3. Education & Public Services: "AI for Vernacular Education and Local Governance Grievance Redressal"

Verifies:
- Dynamic domain discovery without fixed caps
- Domain-sensitive source selection (Kerala, India & Global)
- 10 mandatory quality gates qualification
- 100-point rubric scoring (with General Theme Mode normalization)
- Bounded adversarial debate
- Winner selection / honest rejection mechanics
"""

from __future__ import annotations

from pathlib import Path

import pytest

from config.settings import get_settings
from src.database.repository import Repository
from src.models.hackathon import HackathonInput
from src.models.pipeline import PipelineOptions
from src.orchestration.pipeline import HackathonPipeline
from src.research.sources.kerala_india_registry import KeralaIndiaSourceRegistry
from tests.fakes import FakeIntelligence, FakeLLM, FakeResearch


@pytest.fixture()
def report_dir(tmp_path: Path, monkeypatch):
    settings = get_settings()
    target = tmp_path / "reports"
    monkeypatch.setattr(settings.storage, "reports_dir", target)
    return target


def test_theme_1_agriculture_and_climate(repository: Repository, report_dir: Path):
    """Benchmark Theme 1: Climate-Resilient Agriculture and Rural Communities."""
    theme = "Climate-Resilient Agriculture and Rural Communities"
    registry = KeralaIndiaSourceRegistry()
    recommended_sources = registry.recommend_sources(theme, geography="all", limit=5)
    rec_ids = {s.id for s in recommended_sources}
    assert any(rid in {"KL-002", "KL-003", "KL-007", "IN-002", "IN-003", "GL-001"} for rid in rec_ids)

    llm = FakeLLM(score=8.5)
    research = FakeResearch()
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )

    result = pipeline.run(
        HackathonInput(
            theme=theme,
            name="Kerala Agritech Grand Challenge",
            constraints="Geographical Priority: Kerala First; Target Districts: Wayanad, Alappuzha, Palakkad",
        ),
        PipelineOptions(domain_exploration_budget=8, problems_per_domain=2, max_finalists=3),
    )

    assert result.status == "completed", result.error
    assert result.error is None
    assert result.domain_map is not None
    assert result.domain_map.total_domains_explored >= 3
    assert result.feasibility is not None
    assert len(result.feasibility.candidates) > 0

    assert result.winner is not None and result.winner.has_winner
    winner = result.winner.winner
    assert winner is not None
    assert winner.total_score >= 80.0
    assert len(winner.quality_gates) == 10
    assert winner.all_gates_passed
    assert winner.is_qualified
    assert len(result.report.sections) == 24


def test_theme_2_healthcare_and_epidemiology(repository: Repository, report_dir: Path):
    """Benchmark Theme 2: AI for Rural Telemedicine and Dengue Outbreak Surveillance."""
    theme = "AI for Rural Telemedicine and Dengue Outbreak Surveillance"
    registry = KeralaIndiaSourceRegistry()
    recommended_sources = registry.recommend_sources(theme, geography="all", limit=5)
    rec_ids = {s.id for s in recommended_sources}
    assert any(rid in {"KL-006", "IN-007", "GL-005"} for rid in rec_ids)

    llm = FakeLLM(score=8.0)
    research = FakeResearch()
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )

    result = pipeline.run(
        HackathonInput(
            theme=theme,
            name="",  # General Theme Mode
        ),
        PipelineOptions(domain_exploration_budget=6, problems_per_domain=2, max_finalists=3),
    )

    assert result.status == "completed", result.error
    assert result.winner is not None and result.winner.has_winner
    winner = result.winner.winner
    assert winner is not None
    assert winner.is_general_theme_mode
    assert len(winner.quality_gates) == 10
    assert winner.all_gates_passed
    # In General Theme Mode, normalized score maps assessable criteria
    assert winner.normalized_score >= 70.0


def test_theme_3_education_and_public_governance(repository: Repository, report_dir: Path):
    """Benchmark Theme 3: AI for Vernacular Education and Local Governance Grievance Redressal."""
    theme = "AI for Vernacular Education and Local Governance Grievance Redressal"
    registry = KeralaIndiaSourceRegistry()
    recommended_sources = registry.recommend_sources(theme, geography="all", limit=5)
    rec_ids = {s.id for s in recommended_sources}
    assert any(rid in {"KL-001", "IN-006", "GL-006", "GL-007"} for rid in rec_ids)

    llm = FakeLLM(score=8.2)
    research = FakeResearch()
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )

    result = pipeline.run(
        HackathonInput(
            theme=theme,
            name="Smart Governance Hackathon",
            constraints="Zero paid cloud APIs; Offline capability; Malayalam support",
        ),
        PipelineOptions(domain_exploration_budget=6, problems_per_domain=2, max_finalists=3),
    )

    assert result.status == "completed", result.error
    assert result.winner is not None and result.winner.has_winner
    winner = result.winner.winner
    assert winner is not None
    assert len(winner.quality_gates) == 10
    assert winner.all_gates_passed
    assert result.report is not None
    assert len(result.report.sections) == 24
