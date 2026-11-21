"""Comprehensive tests for the Ten Mandatory Quality Gates and General Theme Mode scoring."""

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
    AdaptabilityClassification,
    ExistingSolution,
    GlobalToLocalAdaptation,
    InnovationGap,
    OpportunityClassification,
)
from src.research.evidence_aggregator import EvidenceAggregator
from src.utils.hackathon_time import utc_now
from tests.fakes import FakeLLM


def _make_problem(evidence_count: int = 2, kerala: bool = True) -> ProblemCandidate:
    return ProblemCandidate(
        id="P01",
        title="Smallholder farmers suffer crop loss from erratic monsoon rains",
        description="Erratic monsoon rainfall leads to severe flooding and crop rot in small homestead plots.",
        domain="Climate-Resilient Agriculture",
        subdomain="Agro-hydrology",
        seriousness="high",
        evidence=[
            ProblemEvidence(
                description=f"Empirical field study {i}",
                source_url=f"https://kau.in/research/paper_{i}",
                source_type="research",
                credibility=0.85,
            )
            for i in range(evidence_count)
        ],
        theme_connection="Directly addresses climate resilience in smallholder agriculture",
        kerala_relevance="Directly impacts Kuttanad below-sea-level paddy polders and Wayanad slopes" if kerala else "",
        india_relevance="Scalable to flood-prone agrarian belts across Assam, Bihar, and coastal Odisha" if kerala else "",
        target_districts=["Alappuzha", "Wayanad"] if kerala else [],
        target_geography="kerala" if kerala else "global",
        confidence=0.85,
    )


def _make_gap(
    classification: OpportunityClassification = OpportunityClassification.DIFFERENTIATED,
    has_solutions: bool = True,
) -> InnovationGap:
    solutions = (
        [
            ExistingSolution(
                name="Central Weather Dashboard",
                solution_type="open_source",
                description="Regional aggregate weather display",
                url="https://github.com/example/weather-dash",
                disadvantages=["Lacks plot-level advisory", "English only", "No offline mode"],
            )
        ]
        if has_solutions
        else []
    )
    return InnovationGap(
        problem_candidate_id="P01",
        classification=classification,
        existing_solutions=solutions,
        gap_description="No localized offline advisory exists for micro-plot farmers.",
        differentiation_potential="Hyper-local offline-first advisory calibrated to sub-hectare Kerala homestead plots.",
        evidence_summary="Extensive review of 3 national systems and 2 open repositories.",
        confidence=0.8,
    )


def _make_candidate(
    *,
    hours: float = 24.0,
    differentiation_len: int = 50,
    has_unavailable_dep: bool = False,
    cost: str = "minimal",
    has_demo_plan: bool = True,
    kerala_adaptation: bool = True,
    risk_count: int = 2,
    has_mitigation: bool = True,
    disadvantage_count: int = 2,
) -> CandidateSolution:
    data_reqs = [
        TechnicalRequirement(
            category="data",
            description="KAU Agromet historical dataset",
            availability="unavailable" if has_unavailable_dep else "available",
            cost="free",
        )
    ]
    risks = [
        RiskAssessment(
            risk_type="technical",
            description=f"Risk factor {i}",
            severity="medium",
            likelihood="possible",
            mitigation=f"Mitigation strategy {i}" if has_mitigation else None,
        )
        for i in range(risk_count)
    ]
    diff_text = "A" * differentiation_len
    cand = CandidateSolution(
        id="C01",
        title="Micro-Plot Agro-Climatic Advisory",
        problem_candidate_id="P01",
        problem_statement="Smallholders suffer from unpredictable monsoon variations without local guidance.",
        proposed_solution="Lightweight offline PWA delivering biophysical guidance using public agro-met feeds.",
        unique_differentiation=diff_text,
        technical_architecture="FastAPI ingestion -> SQLite cache -> Deterministic MCDA envelope filter -> Responsive UI.",
        estimated_hours=hours,
        development_complexity="medium",
        data_requirements=data_reqs,
        risks=risks,
        disadvantages=[f"Disadvantage {i}" for i in range(disadvantage_count)],
        mitigation_strategies=["Cache baseline climatological norms locally"],
        hackathon_demo_plan="Demonstrate 3-minute hero flow using pre-computed Wayanad and Kuttanad farm profiles." if has_demo_plan else "",
        estimated_cost=cost,
        economic_viability_notes="Zero recurring fees; operates on free open datasets and local compute.",
        ethical_sustainability_notes="Respects farmer data sovereignty; recommendations follow KAU standards.",
        domain="Climate-Resilient Agriculture",
        target_districts=["Alappuzha", "Wayanad"],
        target_geography="kerala",
        kerala_adaptation=GlobalToLocalAdaptation(
            global_reference_solution="International CGIAR agro-climatic decision support framework",
            transferability_tier=AdaptabilityClassification.TIER_B_MODIFIED,
            kerala_applicability="Adapted for fragmented homestead gardens (<0.5 ha) and Kuttanad below-sea-level conditions.",
            india_scale_potential="Applicable to other flood-vulnerable agrarian states via IMD gridded products.",
            required_modifications=["Malayalam voice prompt integration", "Offline SQLite storage"],
            local_constraints=["Plot size < 0.5 ha", "Monsoon cloud cover"],
        )
        if kerala_adaptation
        else None,
    )
    return cand


def _make_hackathon(hours: int = 36, name: str = "") -> HackathonInput:
    return HackathonInput(
        name=name,
        theme="Climate-Resilient Agriculture",
        deadline=utc_now() + timedelta(hours=hours),
    )


# -------------------------------------------------------------
# Test Suite: All 10 Gates
# -------------------------------------------------------------

def test_all_ten_gates_pass_successfully():
    service = EvaluationService(FakeLLM(score=8.0))
    cand = _make_candidate()
    prob = _make_problem()
    gap = _make_gap()
    hackathon = _make_hackathon(hours=36)
    intel = HackathonIntelligence(hackathon_input=hackathon)

    eval_result = service.evaluate(cand, prob, gap, hackathon, intel)

    assert len(eval_result.quality_gates) == 10
    assert all(g.name in GATE_NAMES for g in eval_result.quality_gates)
    assert all(g.status.value == "passed" for g in eval_result.quality_gates)
    assert eval_result.all_gates_passed
    assert eval_result.is_qualified


def test_gate1_theme_alignment_failure():
    service = EvaluationService(FakeLLM(score=8.0))
    cand = _make_candidate()
    cand.problem_statement = ""
    prob = _make_problem()
    prob.theme_connection = ""
    cand.proposed_solution = ""
    hackathon = _make_hackathon()
    intel = HackathonIntelligence(hackathon_input=hackathon)

    eval_result = service.evaluate(cand, prob, _make_gap(), hackathon, intel)
    gate = next(g for g in eval_result.quality_gates if g.name == GATE_NAMES[0])
    assert gate.status.value == "failed"
    assert not eval_result.is_qualified


def test_gate2_evidence_validation_failure_single_source():
    service = EvaluationService(FakeLLM(score=8.0))
    cand = _make_candidate()
    prob = _make_problem(evidence_count=1)  # Only 1 source, fails gate 2
    hackathon = _make_hackathon()
    intel = HackathonIntelligence(hackathon_input=hackathon)

    eval_result = service.evaluate(cand, prob, _make_gap(), hackathon, intel)
    gate = next(g for g in eval_result.quality_gates if g.name == GATE_NAMES[1])
    assert gate.status.value == "failed"
    assert not eval_result.is_qualified


def test_gate3_kerala_relevance_failure():
    service = EvaluationService(FakeLLM(score=8.0))
    cand = _make_candidate(kerala_adaptation=False)
    cand.target_districts = []
    cand.target_geography = "global"
    cand.proposed_solution = "Generic worldwide web application"
    prob = _make_problem(kerala=False)
    hackathon = _make_hackathon()
    intel = HackathonIntelligence(hackathon_input=hackathon)

    eval_result = service.evaluate(cand, prob, _make_gap(), hackathon, intel)
    gate = next(g for g in eval_result.quality_gates if g.name == GATE_NAMES[2])
    assert gate.status.value == "failed"
    assert not eval_result.is_qualified


def test_gate4_existing_solution_investigation_failure():
    service = EvaluationService(FakeLLM(score=8.0))
    cand = _make_candidate()
    prob = _make_problem()
    gap = _make_gap(classification=OpportunityClassification.INSUFFICIENT_EVIDENCE, has_solutions=False)
    hackathon = _make_hackathon()
    intel = HackathonIntelligence(hackathon_input=hackathon)

    eval_result = service.evaluate(cand, prob, gap, hackathon, intel)
    gate = next(g for g in eval_result.quality_gates if g.name == GATE_NAMES[3])
    assert gate.status.value == "failed"
    assert not eval_result.is_qualified


def test_gate5_differentiation_failure_short_claim():
    service = EvaluationService(FakeLLM(score=8.0))
    cand = _make_candidate(differentiation_len=15)  # < 30 chars
    prob = _make_problem()
    gap = _make_gap()
    hackathon = _make_hackathon()
    intel = HackathonIntelligence(hackathon_input=hackathon)

    eval_result = service.evaluate(cand, prob, gap, hackathon, intel)
    gate = next(g for g in eval_result.quality_gates if g.name == GATE_NAMES[4])
    assert gate.status.value == "failed"
    assert not eval_result.is_qualified


def test_gate6_global_to_local_adaptability_failure():
    service = EvaluationService(FakeLLM(score=8.0))
    cand = _make_candidate(kerala_adaptation=False)
    prob = _make_problem()
    gap = _make_gap()
    hackathon = _make_hackathon()
    intel = HackathonIntelligence(hackathon_input=hackathon)

    eval_result = service.evaluate(cand, prob, gap, hackathon, intel)
    gate = next(g for g in eval_result.quality_gates if g.name == GATE_NAMES[5])
    assert gate.status.value == "failed"
    assert not eval_result.is_qualified


def test_gate7_technical_feasibility_failure_unavailable_dep():
    service = EvaluationService(FakeLLM(score=8.0))
    cand = _make_candidate(has_unavailable_dep=True)
    prob = _make_problem()
    gap = _make_gap()
    hackathon = _make_hackathon()
    intel = HackathonIntelligence(hackathon_input=hackathon)

    eval_result = service.evaluate(cand, prob, gap, hackathon, intel)
    gate = next(g for g in eval_result.quality_gates if g.name == GATE_NAMES[6])
    assert gate.status.value == "failed"
    assert not eval_result.is_qualified


def test_gate8_economic_viability_failure_prohibitive_cost():
    service = EvaluationService(FakeLLM(score=8.0))
    cand = _make_candidate(cost="prohibitive")
    prob = _make_problem()
    gap = _make_gap()
    hackathon = _make_hackathon()
    intel = HackathonIntelligence(hackathon_input=hackathon)

    eval_result = service.evaluate(cand, prob, gap, hackathon, intel)
    gate = next(g for g in eval_result.quality_gates if g.name == GATE_NAMES[7])
    assert gate.status.value == "failed"
    assert not eval_result.is_qualified


def test_gate9_buildability_failure_deadline_exceeded():
    service = EvaluationService(FakeLLM(score=8.0))
    cand = _make_candidate(hours=120.0)  # > 36h * 1.15 = 41.4h
    prob = _make_problem()
    gap = _make_gap()
    hackathon = _make_hackathon(hours=36)
    intel = HackathonIntelligence(hackathon_input=hackathon)

    eval_result = service.evaluate(cand, prob, gap, hackathon, intel)
    gate = next(g for g in eval_result.quality_gates if g.name == GATE_NAMES[8])
    assert gate.status.value == "failed"
    assert not eval_result.is_qualified


def test_gate10_risk_assessment_failure():
    service = EvaluationService(FakeLLM(score=8.0))
    cand = _make_candidate(risk_count=1)  # Requires >= 2 risks
    prob = _make_problem()
    gap = _make_gap()
    hackathon = _make_hackathon()
    intel = HackathonIntelligence(hackathon_input=hackathon)

    eval_result = service.evaluate(cand, prob, gap, hackathon, intel)
    gate = next(g for g in eval_result.quality_gates if g.name == GATE_NAMES[9])
    assert gate.status.value == "failed"
    assert not eval_result.is_qualified


# -------------------------------------------------------------
# Test Suite: General Theme Mode vs Event Mode Scoring
# -------------------------------------------------------------

def test_general_theme_mode_scoring_normalizes_to_100():
    service = EvaluationService(FakeLLM(score=8.0))
    cand = _make_candidate()
    prob = _make_problem()
    gap = _make_gap()
    # General Theme Mode: no event name provided
    hackathon = _make_hackathon(name="")
    intel = HackathonIntelligence(hackathon_input=hackathon, is_general_theme_mode=True)

    eval_result = service.evaluate(cand, prob, gap, hackathon, intel)

    assert eval_result.is_general_theme_mode
    # Organizer criterion (10 pts) scored 0 and marked not assessable
    organizer_score = next(s for s in eval_result.scores if "organizer" in s.name.lower())
    assert organizer_score.score == 0.0
    assert organizer_score.weighted_score == 0.0
    assert "NOT ASSESSABLE" in organizer_score.justification

    # Remaining 7 assessable criteria total 90 weight; scored at 8.0/10 -> raw = 72.0
    assert eval_result.raw_score == 72.0
    # Normalized score: (72.0 / 90) * 100 = 80.0
    assert round(eval_result.normalized_score, 1) == 80.0
    assert round(eval_result.total_score, 1) == 80.0


def test_event_mode_scores_all_criteria_out_of_100():
    service = EvaluationService(FakeLLM(score=8.0))
    cand = _make_candidate()
    prob = _make_problem()
    gap = _make_gap()
    # Event Mode: specific event name provided
    hackathon = _make_hackathon(name="Smart India Hackathon 2026")
    intel = HackathonIntelligence(hackathon_input=hackathon, is_general_theme_mode=False)

    eval_result = service.evaluate(cand, prob, gap, hackathon, intel)

    assert not eval_result.is_general_theme_mode
    organizer_score = next(s for s in eval_result.scores if "organizer" in s.name.lower())
    assert organizer_score.score == 8.0
    assert organizer_score.weighted_score == 8.0  # 8.0/10 * 10 = 8.0
    assert eval_result.raw_score == 80.0
    assert eval_result.normalized_score == 80.0
    assert eval_result.total_score == 80.0
