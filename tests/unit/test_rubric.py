"""Rubric weighting and mandatory quality-gate tests."""

from __future__ import annotations

from datetime import timedelta

from src.evaluation.rubric import GATE_NAMES, EvaluationService
from src.models.candidate import (
    CandidateSolution,
    RiskAssessment,
    TechnicalRequirement,
)
from src.models.domain import ProblemCandidate, ProblemEvidence
from src.models.hackathon import HackathonInput, HackathonIntelligence
from src.models.research import (
    ExistingSolution,
    InnovationGap,
    OpportunityClassification,
)
from src.utils.hackathon_time import utc_now
from tests.fakes import FakeLLM


def _problem(evidence_count: int = 2) -> ProblemCandidate:
    return ProblemCandidate(
        id="P01",
        title="Commuters lack route-level pollution guidance",
        description="Commuters cannot compare exposure across routes.",
        domain="Urban mobility",
        seriousness="high",
        evidence=[
            ProblemEvidence(
                description=f"Evidence {i}",
                source_url=f"https://example.org/{i}",
                source_type="openalex",
                credibility=0.8,
            )
            for i in range(evidence_count)
        ],
        confidence=0.8,
    )


def _gap(
    classification: OpportunityClassification = OpportunityClassification.DIFFERENTIATED,
) -> InnovationGap:
    return InnovationGap(
        problem_candidate_id="P01",
        classification=classification,
        existing_solutions=[
            ExistingSolution(
                name="Dashboard",
                solution_type="open_source",
                description="City-wide dashboard",
                url="https://github.com/example/dashboard",
                disadvantages=["No routing"],
            )
        ],
        gap_description="No route-level guidance.",
        differentiation_potential="Route-level exposure scoring.",
        evidence_summary="One dashboard and two studies.",
        confidence=0.7,
    )


def _candidate(hours: float = 20) -> CandidateSolution:
    return CandidateSolution(
        id="C01",
        title="Exposure-aware commute coach",
        problem_candidate_id="P01",
        problem_statement="Commuters cannot compare exposure.",
        proposed_solution="Route planner with exposure estimates.",
        unique_differentiation="Route-level explainable exposure trade-offs for commuters.",
        technical_architecture="Ingestion -> grid -> router.",
        estimated_hours=hours,
        development_complexity="medium",
        data_requirements=[
            TechnicalRequirement(
                category="data",
                description="Open air quality data",
                availability="available",
            )
        ],
        risks=[
            RiskAssessment(
                risk_type="data",
                description="Sparse sensors",
                severity="medium",
                likelihood="likely",
                mitigation="Show confidence and fall back to models.",
            ),
            RiskAssessment(
                risk_type="technical",
                description="API limits",
                severity="low",
                likelihood="possible",
                mitigation="Cache routes.",
            ),
        ],
        disadvantages=["Depends on data quality"],
        mitigation_strategies=["Pre-cache demo routes"],
        hackathon_demo_plan="Show two routes.",
        confidence=0.8,
        domain="Urban mobility",
    )


def _hackathon(hours: int = 36) -> HackathonInput:
    return HackathonInput(
        theme="Sustainable cities",
        deadline=utc_now() + timedelta(hours=hours),
    )


def test_all_gates_pass_and_score_is_weighted() -> None:
    service = EvaluationService(FakeLLM(score=8.0))
    evaluation = service.evaluate(
        _candidate(),
        _problem(),
        _gap(),
        _hackathon(),
        HackathonIntelligence(hackathon_input=_hackathon()),
    )
    assert len(evaluation.scores) == 8
    assert round(evaluation.base_score, 1) == 80.0
    assert len(evaluation.quality_gates) == 7
    assert all(g.name in GATE_NAMES for g in evaluation.quality_gates)
    assert evaluation.all_gates_passed
    assert evaluation.is_qualified


def test_missing_evidence_fails_gate_despite_high_score() -> None:
    service = EvaluationService(FakeLLM(score=10.0))
    evaluation = service.evaluate(
        _candidate(),
        _problem(evidence_count=0),
        _gap(),
        _hackathon(),
        HackathonIntelligence(hackathon_input=_hackathon()),
    )
    evidence_gate = next(g for g in evaluation.quality_gates if g.name == GATE_NAMES[0])
    assert evidence_gate.status.value == "failed"
    assert not evaluation.is_qualified
    assert evaluation.total_score == 100.0  # high score must not hide the failure


def test_commonly_solved_fails_originality_gate() -> None:
    service = EvaluationService(FakeLLM())
    evaluation = service.evaluate(
        _candidate(),
        _problem(),
        _gap(OpportunityClassification.COMMONLY_SOLVED),
        _hackathon(),
        HackathonIntelligence(hackathon_input=_hackathon()),
    )
    gate = next(g for g in evaluation.quality_gates if g.name == GATE_NAMES[2])
    assert gate.status.value == "failed"
    assert not evaluation.is_qualified


def test_unrealistic_hours_fail_deadline_gate() -> None:
    service = EvaluationService(FakeLLM())
    evaluation = service.evaluate(
        _candidate(hours=200),
        _problem(),
        _gap(),
        _hackathon(hours=36),
        HackathonIntelligence(hackathon_input=_hackathon(hours=36)),
    )
    gate = next(g for g in evaluation.quality_gates if g.name == GATE_NAMES[4])
    assert gate.status.value == "failed"
    assert not evaluation.is_qualified
