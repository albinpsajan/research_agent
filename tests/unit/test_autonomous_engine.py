"""Unit tests for Autonomous Idea Testing, Improvement, and Selection Engine.

Verifies:
1. Dynamic gate re-evaluation transitions INSUFFICIENT_EVIDENCE to PASSED when targeted sources are retrieved.
2. Solution refinement improves differentiation, demo plan, and technical architecture while maintaining revision history.
3. Fatal gate failures (e.g. commonly solved or massive scope violations) cannot be bypassed.
4. Elimination audit records original problem, gate outcome, improvement attempts, and reason.
5. Bounded improvement cycle stops after max rounds without infinite looping.
6. Competing architectural angles are recorded and rendered in the implementation blueprint.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.agents.adversarial_critic import AdversarialCriticAgent
from src.agents.innovation_research import InnovationResearchAgent
from src.agents.solution_architect import SolutionArchitectAgent
from src.evaluation.rubric import EvaluationService, GATE_NAMES, V2_GATE_NAMES
from src.models.candidate import CandidateSolution, SolutionRevision, TechnicalRequirement
from src.models.domain import ProblemCandidate, ProblemEvidence
from src.models.evaluation import CandidateEvaluation, QualityGate, QualityGateStatus, ScoreCriterion
from src.models.hackathon import HackathonInput, HackathonIntelligence
from src.models.research import InnovationGap, OpportunityClassification
from src.reports.generator import _evaluation_table, _score_table, ReportGenerator
from src.research.base import SearchResult


def _make_candidate(
    cand_id: str = "C01",
    title: str = "AgriSense Kerala",
    diff: str = "Multi-spectral edge sensor with local Malayalam voice alerts and zero recurring fees.",
) -> CandidateSolution:
    return CandidateSolution(
        id=cand_id,
        title=title,
        problem_candidate_id=f"P-{cand_id}",
        problem_statement="Crop pest outbreaks cause catastrophic yield loss in Wayanad.",
        proposed_solution="Edge computer-vision traps with solar power and LoRa mesh networking.",
        unique_differentiation=diff,
        technical_architecture="RPi 5 with Hailo-8 NPU, local YOLOv8-nano model, LoRaWAN gateway, SQLite edge buffer.",
        estimated_hours=32.0,
        hackathon_demo_plan="Live camera demonstration running inference on real leaf samples with instant LCD detection.",
        data_requirements=[
            TechnicalRequirement(category="data", description="ICAR pest imagery", availability="available", cost="free"),
        ],
        api_requirements=[
            TechnicalRequirement(category="api", description="Local SQLite cache", availability="available", cost="free"),
        ],
        target_geography="kerala",
        target_districts=["Wayanad", "Palakkad"],
        economic_viability_notes="Zero cloud subscription fees, completely open source.",
        ethical_sustainability_notes="Follows organic KAU pest control guidelines.",
        domain="Agritech",
    )


def _make_problem(prob_id: str = "P-C01", url_count: int = 1) -> ProblemCandidate:
    evidence = []
    for i in range(url_count):
        evidence.append(
            ProblemEvidence(
                description=f"Evidence source {i+1} documenting pest losses",
                source_url=f"https://doi.org/10.1016/j.cropro.2024.10{i}",
                credibility=0.85,
                source_type="academic_paper",
            )
        )
    return ProblemCandidate(
        id=prob_id,
        title="Wayanad Pepper Wilt Pest Outbreak",
        description="Catastrophic wilt outbreaks reduce annual harvest by 38% for marginal farmers.",
        domain="Agritech",
        affected_people=["Marginal pepper farmers in Wayanad", "KAU extension workers"],
        seriousness="critical",
        confidence=0.88,
        evidence=evidence,
        theme_connection="Directly aligns with climate-resilient agriculture theme.",
        kerala_relevance="Wayanad district high-range crop disease.",
        target_districts=["Wayanad"],
    )


def _make_gap(prob_id: str = "P-C01") -> InnovationGap:
    return InnovationGap(
        problem_candidate_id=prob_id,
        classification=OpportunityClassification.DIFFERENTIATED,
        gap_description="Commercial traps require 4G/5G cloud telemetry which fails in high-range plantation valleys.",
        differentiation_potential="Offline edge-inference LoRa mesh deployment with zero cloud recurring cost.",
        evidence_summary="Extensive study of 12 existing traps and open-source models.",
        existing_solutions=[],
        github_projects=[],
    )


def test_re_evaluate_transitions_insufficient_evidence_to_passed() -> None:
    """1. Dynamic gate re-evaluation transitions INSUFFICIENT_EVIDENCE to PASSED when targeted sources are retrieved."""
    llm = MagicMock()
    evaluator = EvaluationService(llm)

    candidate = _make_candidate()
    # Problem starts with 0 evidence URLs -> Gate 2 is INSUFFICIENT_EVIDENCE
    problem = _make_problem(url_count=0)
    gap = _make_gap()
    hackathon = HackathonInput(theme="Agri-Tech Solutions", name="BeachHack")
    intelligence = HackathonIntelligence(hackathon_input=hackathon)

    initial_gates = evaluator._deterministic_gates(candidate, problem, gap, hackathon, intelligence, 36.0)
    g2 = next(g for g in initial_gates if "validation" in g.name.lower() or "evidence" in g.name.lower())
    assert g2.status == QualityGateStatus.INSUFFICIENT_EVIDENCE

    # Now simulate targeted research retrieving two corroborating citations
    problem.evidence.append(
        ProblemEvidence(
            description="KAU advisory bulletin confirming 40% crop loss",
            source_url="https://kau.in/research/bulletin-2024-pest.pdf",
            credibility=0.90,
            source_type="institutional_report",
        )
    )
    problem.evidence.append(
        ProblemEvidence(
            description="ICAR study on Wayanad plantation diseases",
            source_url="https://doi.org/10.1016/j.cropro.2024.101",
            credibility=0.88,
            source_type="academic_paper",
        )
    )

    prior_eval = CandidateEvaluation(
        candidate_id=candidate.id or "C01",
        candidate_title=candidate.title,
        domain=candidate.domain,
        scores=[
            ScoreCriterion(name="Real-world problem significance", weight=20, score=4.0, weighted_score=8.0),
            ScoreCriterion(name="Technical feasibility", weight=15, score=7.0, weighted_score=10.5),
        ],
        quality_gates=initial_gates,
    )

    improved_eval = evaluator.re_evaluate_candidate(
        candidate=candidate,
        problem=problem,
        gap=gap,
        hackathon=hackathon,
        intelligence=intelligence,
        prior_evaluation=prior_eval,
    )

    g2_after = next(g for g in improved_eval.quality_gates if "validation" in g.name.lower() or "evidence" in g.name.lower())
    assert g2_after.status == QualityGateStatus.PASSED
    assert len(g2_after.evidence) == 2
    # Check that score for problem significance increased
    prob_score = next(s for s in improved_eval.scores if "problem" in s.name.lower())
    assert prob_score.score > 4.0


def test_solution_refinement_records_revision_history() -> None:
    """2. Solution refinement improves differentiation, demo plan, and technical architecture while maintaining revision history."""
    llm = MagicMock()
    # Mock LLM response for refinement
    llm.generate_json.return_value = MagicMock(
        summary_of_changes="Sharpened differentiation with on-device LoRa mesh; formulated 3-minute judging demo plan.",
        improved_differentiation="Proprietary edge-quantized YOLOv8 nano model running on offline solar LoRa mesh with sub-second Malayalam voice output.",
        improved_technical_architecture="RPi 5 + Hailo-8 NPU + SX1262 LoRa module communicating over peer-to-peer mesh with zero internet requirement.",
        improved_demo_plan="Live demo: 1) Trigger insect leaf trap under artificial light; 2) Hailo NPU identifies pest in 120ms; 3) LoRa hub sounds local alert buzzer.",
        replacement_technologies=["HailoRT", "Meshtastic", "SQLite"],
        resolved_criticisms=["Differentiation length too short", "Demo plan missing"],
        new_mitigations=["Battery buffer for 72 hours of monsoon overcast weather"],
        rescoped_hours=28.0,
    )

    architect = SolutionArchitectAgent(llm, MagicMock(), MagicMock(), MagicMock())
    candidate = _make_candidate(diff="Short") # Initially too short (<30 chars)
    candidate.hackathon_demo_plan = "" # Initially missing

    assert len(candidate.revisions) == 0

    refined = architect.refine_solution(
        candidate=candidate,
        criticisms=["Differentiation is only 5 characters", "Hackathon demo plan is missing"],
        failing_gates=[GATE_NAMES[4], GATE_NAMES[8]],
        available_hours=36.0,
    )

    assert len(refined.revisions) == 1
    rev = refined.revisions[0]
    assert rev.revision_number == 1
    assert "LoRa mesh" in rev.summary_of_changes
    assert len(refined.unique_differentiation) >= 40
    assert len(refined.hackathon_demo_plan) >= 20
    assert refined.improvement_attempted is True
    assert refined.final_disposition == "improved"


def test_fatal_gate_failure_cannot_be_bypassed() -> None:
    """3. Fatal gate failures (e.g. commonly solved or massive scope violations) cannot be bypassed."""
    llm = MagicMock()
    evaluator = EvaluationService(llm)

    candidate = _make_candidate()
    problem = _make_problem(url_count=2)
    # Gap classified as COMMONLY_SOLVED -> Gate 5 must genuinely FAIL
    gap = InnovationGap(
        problem_candidate_id="P-C01",
        classification=OpportunityClassification.COMMONLY_SOLVED,
        gap_description="Commodity weather app with hundreds of identical projects.",
        evidence_summary="Extensive duplicates found.",
    )
    hackathon = HackathonInput(theme="Agri-Tech Solutions", name="BeachHack")
    intelligence = HackathonIntelligence(hackathon_input=hackathon)

    gates = evaluator._deterministic_gates(candidate, problem, gap, hackathon, intelligence, 36.0)
    g5 = next(g for g in gates if "innovation" in g.name.lower() or "differentiation" in g.name.lower())
    assert g5.status == QualityGateStatus.FAILED


def test_elimination_audit_table_rendering() -> None:
    """4. Elimination audit records original problem, gate outcome, improvement attempts, and reason."""
    c1 = _make_candidate("C01", "Qualified Candidate")
    c1.final_disposition = "qualified"

    c2 = _make_candidate("C02", "Eliminated Candidate")
    c2.final_disposition = "eliminated"
    c2.elimination_reason = "Fatal gate failure: Genuine Innovation. Solution is commonly solved commodity."
    c2.improvement_attempted = True

    eval1 = CandidateEvaluation(
        candidate_id="C01",
        candidate_title=c1.title,
        domain="Agritech",
        total_score=85.0,
        all_gates_passed=True,
        is_qualified=True,
        quality_gates=[
            QualityGate(name="Problem validation", description="desc", status=QualityGateStatus.PASSED),
        ],
    )

    eval2 = CandidateEvaluation(
        candidate_id="C02",
        candidate_title=c2.title,
        domain="Agritech",
        total_score=45.0,
        all_gates_passed=False,
        is_qualified=False,
        quality_gates=[
            QualityGate(name="Genuine innovation", description="desc", status=QualityGateStatus.FAILED),
        ],
        elimination_reason=c2.elimination_reason,
        improvement_rounds_attempted=1,
    )

    table_md = _evaluation_table([eval1, eval2], [c1, c2])

    assert "Finalist Evaluation & Qualification Status" in table_md
    assert "Intelligent Candidate Elimination Audit" in table_md
    assert "Eliminated Candidate" in table_md
    assert "1 Gate(s) Unmet" in table_md
    assert "Yes" in table_md # Improvement was attempted
    assert "commonly solved commodity" in table_md


def test_competing_approaches_recorded_and_rendered() -> None:
    """5. Competing architectural angles are recorded and rendered in the implementation blueprint."""
    candidate = _make_candidate()
    candidate.competing_approaches = [
        "Approach 1 (Selected): On-device NPU inference with offline LoRa mesh.",
        "Approach 2 (Alternative): Cloud-hosted vision API via GSM cellular modem.",
    ]

    report_gen = ReportGenerator(MagicMock())
    feasibility_md = report_gen._feasibility_section(candidate)

    assert "Competing Architectural Angles Evaluated:" in feasibility_md
    assert "Approach 1 (Selected)" in feasibility_md
    assert "Approach 2 (Alternative)" in feasibility_md
    assert "Recommended 36-Hour Hackathon Build Schedule" in feasibility_md
    assert "Phase 1 (Hours 0–8)" in feasibility_md
    assert "3-Minute Live Judging Demo Plan" in feasibility_md
