"""The agreed 100-point rubric plus mandatory quality gates.

The LLM proposes scores and justifications; deterministic checks can veto a
gate.  A high total score can never hide a failed mandatory gate.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from config.logging_config import get_logger
from config.settings import EvaluationSettings, get_settings
from src.llm.client import LLMClientProtocol
from src.models.candidate import CandidateSolution
from src.models.domain import ProblemCandidate
from src.models.evaluation import (
    CandidateEvaluation,
    QualityGate,
    QualityGateStatus,
    ScoreCriterion,
)
from src.models.hackathon import HackathonInput, HackathonIntelligence
from src.models.research import InnovationGap, OpportunityClassification
from src.research.evidence_aggregator import EvidenceAggregator
from src.utils.hackathon_time import available_hours, deadline_note

logger = get_logger("evaluation.rubric")

GATE_NAMES = (
    "Hackathon theme and judging alignment",
    "Real-world problem validation",
    "Kerala and India relevance",
    "Existing-solution investigation",
    "Genuine innovation and differentiation",
    "Global-to-local adaptability",
    "Technical feasibility and data availability",
    "Economic and practical viability",
    "Hackathon buildability and demonstration",
    "Risk, ethics and sustainability",
)

SYSTEM = """You are the independent evaluator for HackathonIQ.
Score the candidate against the agreed rubric. You are NOT the architect and
must not defend the idea. Every score needs a specific justification grounded
in the supplied evidence. Do not award 10/10 unless the evidence is exceptional;
most strong hackathon ideas score 6-8. A high total cannot excuse a failed
mandatory gate. If evidence is missing, say so and score lower. Return JSON only.
"""


class CriterionScoreLLM(BaseModel):
    name: str
    score: float = Field(default=0, ge=0, le=10)
    justification: str = ""
    evidence: list[str] = Field(default_factory=list)


class GateLLM(BaseModel):
    name: str
    status: str = "warning"
    justification: str = ""


class EvaluationLLM(BaseModel):
    scores: list[CriterionScoreLLM] = Field(default_factory=list)
    gates: list[GateLLM] = Field(default_factory=list)
    overall_assessment: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (value or "").lower()).strip()


def _match_criterion(name: str, weights: dict[str, int]) -> str | None:
    normalized = _normalize(name)
    if not normalized:
        return None
    for criterion in weights:
        target = _normalize(criterion)
        if normalized == target or normalized in target or target in normalized:
            return criterion
    keyword_map = {
        "significance": "Real-world problem significance",
        "problem": "Real-world problem significance",
        "originality": "Originality and differentiation",
        "differentiation": "Originality and differentiation",
        "technical": "Technical feasibility",
        "feasibility": "Technical feasibility",
        "theme": "Hackathon theme relevance",
        "relevance": "Hackathon theme relevance",
        "organizer": "Organizer and sponsor alignment",
        "sponsor": "Organizer and sponsor alignment",
        "alignment": "Organizer and sponsor alignment",
        "innovation": "Innovation and future potential",
        "future": "Innovation and future potential",
        "deadline": "Implementation within deadline",
        "implementation": "Implementation within deadline",
        "demonstration": "Demonstration and judging appeal",
        "demo": "Demonstration and judging appeal",
        "judging": "Demonstration and judging appeal",
    }
    for keyword, criterion in keyword_map.items():
        if keyword in normalized:
            return criterion
    return None


def _match_gate(name: str) -> str | None:
    normalized = _normalize(name)
    keyword_map = {
        # Gate 1: Theme & judging alignment (also matches legacy compliance)
        "theme": GATE_NAMES[0],
        "judging": GATE_NAMES[0],
        "rules": GATE_NAMES[0],
        "compliance": GATE_NAMES[0],
        "compliance with hackathon rules": GATE_NAMES[0],
        # Gate 2: Real-world problem validation (also matches legacy evidence)
        "evidence": GATE_NAMES[1],
        "validation": GATE_NAMES[1],
        "credible evidence of the problem": GATE_NAMES[1],
        "problem validation": GATE_NAMES[1],
        # Gate 3: Kerala and India relevance
        "kerala": GATE_NAMES[2],
        "india": GATE_NAMES[2],
        "relevance": GATE_NAMES[2],
        "kerala and india relevance": GATE_NAMES[2],
        # Gate 4: Existing-solution investigation
        "existing": GATE_NAMES[3],
        "solution investigation": GATE_NAMES[3],
        "existing-solution investigation": GATE_NAMES[3],
        # Gate 5: Genuine innovation and differentiation (also matches legacy originality)
        "originality": GATE_NAMES[4],
        "differentiation": GATE_NAMES[4],
        "honest originality classification": GATE_NAMES[4],
        "genuine innovation and differentiation": GATE_NAMES[4],
        # Gate 6: Global-to-local adaptability
        "adaptability": GATE_NAMES[5],
        "global": GATE_NAMES[5],
        "adaptation": GATE_NAMES[5],
        "global-to-local adaptability": GATE_NAMES[5],
        # Gate 7: Technical feasibility and data availability (also matches legacy practical)
        "technical": GATE_NAMES[6],
        "feasibility": GATE_NAMES[6],
        "practical implementation path": GATE_NAMES[6],
        "technical feasibility and data availability": GATE_NAMES[6],
        "data availability": GATE_NAMES[6],
        # Gate 8: Economic and practical viability
        "economic": GATE_NAMES[7],
        "viability": GATE_NAMES[7],
        "cost": GATE_NAMES[7],
        "economic and practical viability": GATE_NAMES[7],
        # Gate 9: Hackathon buildability and demonstration (also matches legacy deadline)
        "deadline": GATE_NAMES[8],
        "buildability": GATE_NAMES[8],
        "demonstration": GATE_NAMES[8],
        "demo": GATE_NAMES[8],
        "realistic hackathon deadline": GATE_NAMES[8],
        "hackathon buildability and demonstration": GATE_NAMES[8],
        # Gate 10: Risk, ethics and sustainability (also matches legacy risk assessment)
        "risk": GATE_NAMES[9],
        "disadvantage": GATE_NAMES[9],
        "ethics": GATE_NAMES[9],
        "sustainability": GATE_NAMES[9],
        "risk and disadvantage assessment": GATE_NAMES[9],
        "risk ethics and sustainability": GATE_NAMES[9],
    }
    for keyword, gate in keyword_map.items():
        if keyword in normalized:
            return gate
    return None


class EvaluationService:
    """Scores candidates and enforces the seven mandatory quality gates."""

    def __init__(
        self,
        llm: LLMClientProtocol,
        settings: EvaluationSettings | None = None,
    ) -> None:
        self.llm = llm
        self.settings = settings or get_settings().evaluation
        if self.settings.total_weight != 100:
            raise ValueError(
                f"Evaluation rubric must total 100, got {self.settings.total_weight}"
            )

    def evaluate(
        self,
        candidate: CandidateSolution,
        problem: ProblemCandidate | None,
        gap: InnovationGap | None,
        hackathon: HackathonInput,
        intelligence: HackathonIntelligence,
    ) -> CandidateEvaluation:
        weights = self.settings.as_weights()
        hours = available_hours(hackathon)
        is_general_theme = (
            not bool(hackathon.name and hackathon.name.strip())
            or getattr(intelligence, "is_general_theme_mode", False)
            or (hackathon.name or "").lower().strip() in {"none", "unknown", "general theme", "general"}
        )

        prompt = self._prompt(candidate, problem, gap, hackathon, intelligence, hours)
        result = self.llm.generate_json(prompt, EvaluationLLM, SYSTEM)

        by_criterion: dict[str, CriterionScoreLLM] = {}
        for item in result.scores:
            matched = _match_criterion(item.name, weights)
            if matched and matched not in by_criterion:
                by_criterion[matched] = item

        scores: list[ScoreCriterion] = []
        for criterion, weight in weights.items():
            if is_general_theme and ("organizer" in criterion.lower() or "sponsor" in criterion.lower()):
                scores.append(
                    ScoreCriterion(
                        name=criterion,
                        weight=weight,
                        score=0.0,
                        weighted_score=0.0,
                        justification=(
                            "NOT ASSESSABLE: General Theme Mode active (no organizer or sponsors specified). "
                            "Excluded from raw score; overall score normalized over assessable 90 points."
                        ),
                        evidence=["General Theme Mode active"],
                    )
                )
                continue

            item = by_criterion.get(criterion)
            score = max(0.0, min(float(item.score), 10.0)) if item else 0.0
            scores.append(
                ScoreCriterion(
                    name=criterion,
                    weight=weight,
                    score=round(score, 1),
                    weighted_score=round(score / 10.0 * weight, 2),
                    justification=(
                        item.justification
                        if item and item.justification
                        else "The model did not justify this criterion; scored zero."
                    ),
                    evidence=item.evidence[:6] if item else [],
                )
            )

        gates = self._deterministic_gates(
            candidate, problem, gap, hackathon, intelligence, hours
        )
        llm_gates = {}
        for item in result.gates:
            matched = _match_gate(item.name)
            if matched and matched not in llm_gates:
                llm_gates[matched] = item
        for gate in gates:
            llm_gate = llm_gates.get(gate.name)
            if not llm_gate:
                continue
            if (llm_gate.status or "").lower() == "failed":
                gate.status = QualityGateStatus.FAILED
                gate.justification = (
                    f"{gate.justification} Independent evaluator objection: "
                    f"{llm_gate.justification}"
                ).strip()
            elif llm_gate.justification:
                gate.justification = (
                    f"{gate.justification} {llm_gate.justification}".strip()
                )

        evaluation = CandidateEvaluation(
            candidate_id=candidate.id or "",
            candidate_title=candidate.title or candidate.problem_statement[:120],
            domain=candidate.domain,
            scores=scores,
            quality_gates=gates,
            is_general_theme_mode=is_general_theme,
            overall_assessment=result.overall_assessment,
            strengths=result.strengths[:8],
            weaknesses=result.weaknesses[:8],
        )
        evaluation.calculate_total()
        return evaluation

    # ------------------------------------------------------------------
    # Scoring prompt
    # ------------------------------------------------------------------

    def _prompt(
        self,
        candidate: CandidateSolution,
        problem: ProblemCandidate | None,
        gap: InnovationGap | None,
        hackathon: HackathonInput,
        intelligence: HackathonIntelligence,
        hours: float,
    ) -> str:
        weights = "\n".join(
            f"- {name}: weight {weight}"
            for name, weight in self.settings.as_weights().items()
        )
        evidence = (
            "\n".join(
                f"- {item.description[:300]} | {item.source_url or 'no URL'} | "
                f"credibility={item.credibility:.2f}"
                for item in (problem.evidence if problem else [])
            )
            or "- No problem evidence recorded."
        )
        existing = (
            "\n".join(
                f"- {solution.name}: {solution.description[:250]} | "
                f"limitations: {', '.join(solution.disadvantages[:3]) or 'not documented'}"
                for solution in (gap.existing_solutions if gap else [])
            )
            or "- No verified existing solution recorded."
        )
        github = (
            "\n".join(
                f"- {project.name}: {project.stars} stars, active={project.is_active}, "
                f"{project.description or ''}"
                for project in (gap.github_projects if gap else [])
            )
            or "- No GitHub project recorded."
        )
        adaptation_summary = (
            f"Transferability Tier: {candidate.kerala_adaptation.transferability_tier.value if candidate.kerala_adaptation else 'unspecified'}\n"
            f"Kerala Applicability: {candidate.kerala_adaptation.kerala_applicability if candidate.kerala_adaptation else 'unspecified'}\n"
            f"India Scale Potential: {candidate.kerala_adaptation.india_scale_potential if candidate.kerala_adaptation else 'unspecified'}"
        )
        return f"""Hackathon theme: {hackathon.theme}
Hackathon name: {hackathon.name or "not supplied"}
Deadline: {hackathon.deadline.isoformat() if hackathon.deadline else "not supplied"}
Hours available: {hours:.1f}
Organiser goals: {intelligence.organizer_goals[:6]}
Organiser priorities: {intelligence.recurring_priorities[:6]}
Technical restrictions: {intelligence.technical_restrictions[:6]}
User constraints: {hackathon.constraints or "none"}

CANDIDATE
Title: {candidate.title}
Domain: {candidate.domain}
Problem: {candidate.problem_statement}
Target users: {candidate.target_users}
Pain point: {candidate.user_pain_point}
Proposed solution: {candidate.proposed_solution}
Differentiation: {candidate.unique_differentiation}
Gap: {candidate.identified_gap}
Architecture: {candidate.technical_architecture}
Complexity: {candidate.development_complexity}
Estimated hours: {candidate.estimated_hours}
Data requirements: {[r.description + " (" + r.availability + ")" for r in candidate.data_requirements]}
API requirements: {[r.description + " (" + r.availability + ")" for r in candidate.api_requirements]}
Risks: {[r.description + " -> " + (r.mitigation or "no mitigation") for r in candidate.risks]}
Advantages: {candidate.advantages}
Disadvantages: {candidate.disadvantages}
Demo plan: {candidate.hackathon_demo_plan}
Economic viability: {candidate.economic_viability_notes}
Ethical & sustainability: {candidate.ethical_sustainability_notes}

GLOBAL-TO-LOCAL ADAPTATION (KERALA & INDIA):
{adaptation_summary}

PROBLEM EVIDENCE
{evidence}

EXISTING SOLUTIONS
{existing}

REAL GITHUB PROJECTS
{github}

INNOVATION CLASSIFICATION: {gap.classification.value if gap else "unknown"}
GAP: {gap.gap_description if gap else "unknown"}
DIFFERENTIATION POTENTIAL: {gap.differentiation_potential if gap else "unknown"}

RUBRIC (score each 0-10 with a specific justification):
{weights}

MANDATORY GATES (evaluate honestly):
{chr(10).join("- " + name for name in GATE_NAMES)}

Return all eight rubric criteria exactly once, all ten gates, an overall
assessment, strengths and weaknesses. Do not inflate scores."""

    # ------------------------------------------------------------------
    # Deterministic gates
    # ------------------------------------------------------------------

    def _deterministic_gates(
        self,
        candidate: CandidateSolution,
        problem: ProblemCandidate | None,
        gap: InnovationGap | None,
        hackathon: HackathonInput,
        intelligence: HackathonIntelligence,
        hours: float,
    ) -> list[QualityGate]:
        gates: list[QualityGate] = []

        # Gate 1: Hackathon Theme and Official Judging Alignment
        restrictions = intelligence.technical_restrictions + (
            [hackathon.constraints] if hackathon.constraints else []
        )
        is_general = (
            not bool(hackathon.name and hackathon.name.strip())
            or getattr(intelligence, "is_general_theme_mode", False)
            or (hackathon.name or "").lower().strip() in {"none", "unknown", "general theme", "general"}
        )
        theme_aligned = bool(
            (problem and problem.theme_connection)
            or candidate.problem_statement.strip()
            or candidate.proposed_solution.strip()
        )
        gate1_fail = "" if theme_aligned else EvidenceAggregator.classify_gate_failure(GATE_NAMES[0], candidate, problem, gap)
        gates.append(
            QualityGate(
                name=GATE_NAMES[0],
                description="The candidate directly aligns with hackathon theme goals and judging intent.",
                status=QualityGateStatus.PASSED if theme_aligned else QualityGateStatus.FAILED,
                justification=(
                    f"Aligned with theme '{hackathon.theme}'. Mode: {'General Theme Mode (unbiased theme focus)' if is_general else 'Event Mode'}."
                    + (f" Constraints checked: {'; '.join(restrictions[:3])}" if restrictions else "")
                    + (f" [{gate1_fail}]" if gate1_fail else "")
                ),
            )
        )

        # Gate 2: Real-World Problem Validation (>= 2 independent sources, cred >= 0.6)
        evidence = problem.evidence if problem else []
        urls = {e.source_url for e in evidence if e.source_url}
        max_credibility = max((e.credibility for e in evidence), default=0.0)
        credible = len(urls) >= 2 and max_credibility >= 0.6
        gate2_fail = "" if credible else EvidenceAggregator.classify_gate_failure(GATE_NAMES[1], candidate, problem, gap)
        gates.append(
            QualityGate(
                name=GATE_NAMES[1],
                description="At least two independent, credible sources support the problem existence.",
                status=QualityGateStatus.PASSED if credible else QualityGateStatus.FAILED,
                justification=(
                    f"{len(urls)} distinct evidence URL(s); highest credibility {max_credibility:.2f}."
                    + (f" [{gate2_fail}]" if gate2_fail else "")
                ),
                evidence=sorted(urls)[:8],
            )
        )

        # Gate 3: Kerala and India Relevance
        has_kerala = bool(
            candidate.target_districts
            or (candidate.kerala_adaptation and candidate.kerala_adaptation.kerala_applicability.strip())
            or (problem and (problem.kerala_relevance.strip() or problem.india_relevance.strip() or problem.target_districts))
            or "kerala" in candidate.proposed_solution.lower()
            or "india" in candidate.proposed_solution.lower()
            or "kerala" in (problem.description.lower() if problem else "")
            or candidate.target_geography in {"kerala", "india"}
        )
        gate3_fail = "" if has_kerala else EvidenceAggregator.classify_gate_failure(GATE_NAMES[2], candidate, problem, gap)
        districts_str = ", ".join(candidate.target_districts[:4]) if candidate.target_districts else "State-wide Kerala"
        gates.append(
            QualityGate(
                name=GATE_NAMES[2],
                description="Problem directly addresses Kerala ecological/civic realities with Indian scalability.",
                status=QualityGateStatus.PASSED if has_kerala else QualityGateStatus.FAILED,
                justification=(
                    f"Geographical focus: {candidate.target_geography.upper()}; Districts: {districts_str}."
                    + (f" [{gate3_fail}]" if gate3_fail else "")
                ),
                evidence=candidate.target_districts[:6],
            )
        )

        # Gate 4: Existing-Solution Investigation
        existing_count = (
            len(gap.existing_solutions) + len(gap.github_projects) if gap else 0
        )
        has_summary = bool(gap and gap.evidence_summary and gap.evidence_summary.strip())
        investigated = bool(
            gap
            and gap.classification != OpportunityClassification.INSUFFICIENT_EVIDENCE
            and existing_count > 0
            and has_summary
        )
        gate4_fail = "" if investigated else EvidenceAggregator.classify_gate_failure(GATE_NAMES[3], candidate, problem, gap)
        gates.append(
            QualityGate(
                name=GATE_NAMES[3],
                description="Real existing solutions or repositories were investigated.",
                status=QualityGateStatus.PASSED if investigated else QualityGateStatus.FAILED,
                justification=(
                    f"{existing_count} existing solution/repository record(s); "
                    f"classification={gap.classification.value if gap else 'none'}."
                    + (f" [{gate4_fail}]" if gate4_fail else "")
                ),
                evidence=([s.url for s in gap.existing_solutions if s.url][:8] if gap else []),
            )
        )

        # Gate 5: Genuine Innovation and Differentiation
        originality_ok = bool(
            gap
            and gap.classification
            in {
                OpportunityClassification.DIFFERENTIATED,
                OpportunityClassification.UNDERSERVED,
                OpportunityClassification.LIMITED_SOLUTION,
            }
            and len(candidate.unique_differentiation.strip()) >= 30
        )
        gate5_fail = "" if originality_ok else EvidenceAggregator.classify_gate_failure(GATE_NAMES[4], candidate, problem, gap)
        gates.append(
            QualityGate(
                name=GATE_NAMES[4],
                description="Originality is classified honestly and differentiation is stated (>=30 chars).",
                status=QualityGateStatus.PASSED if originality_ok else QualityGateStatus.FAILED,
                justification=(
                    f"Classification: {gap.classification.value if gap else 'none'}; "
                    f"differentiation length: {len(candidate.unique_differentiation)} chars."
                    + (f" [{gate5_fail}]" if gate5_fail else "")
                ),
                evidence=[gap.differentiation_potential] if gap and gap.differentiation_potential else [],
            )
        )

        # Gate 6: Global-to-Local Adaptability
        adaptability_ok = bool(
            candidate.kerala_adaptation
            and candidate.kerala_adaptation.kerala_applicability.strip()
        )
        gate6_fail = "" if adaptability_ok else EvidenceAggregator.classify_gate_failure(GATE_NAMES[5], candidate, problem, gap)
        tier_val = (
            candidate.kerala_adaptation.transferability_tier.value
            if candidate.kerala_adaptation
            else "none"
        )
        gates.append(
            QualityGate(
                name=GATE_NAMES[5],
                description="Global solutions are adapted through 5-tier taxonomy with local constraints.",
                status=QualityGateStatus.PASSED if adaptability_ok else QualityGateStatus.FAILED,
                justification=(
                    f"Transferability: {tier_val}; "
                    f"Modifications: {len(candidate.kerala_adaptation.required_modifications) if candidate.kerala_adaptation else 0} identified."
                    + (f" [{gate6_fail}]" if gate6_fail else "")
                ),
            )
        )

        # Gate 7: Technical Feasibility and Data Availability
        unavailable = [
            req.description
            for req in candidate.data_requirements + candidate.api_requirements
            if req.availability == "unavailable"
        ]
        practical = bool(
            candidate.proposed_solution.strip()
            and candidate.technical_architecture.strip()
            and candidate.estimated_hours
            and candidate.estimated_hours > 0
            and not unavailable
        )
        gate7_fail = "" if practical else EvidenceAggregator.classify_gate_failure(GATE_NAMES[6], candidate, problem, gap)
        gates.append(
            QualityGate(
                name=GATE_NAMES[6],
                description="A concrete architecture and available data/API path exist.",
                status=QualityGateStatus.PASSED if practical else QualityGateStatus.FAILED,
                justification=(
                    ("Solution and architecture are specified with available dependencies."
                     if practical
                     else f"Missing architecture/solution or unavailable dependencies: {unavailable[:4]}")
                    + (f" [{gate7_fail}]" if gate7_fail else "")
                ),
            )
        )

        # Gate 8: Economic and Practical Viability
        cost_ok = candidate.estimated_cost.lower() not in {"prohibitive", "expensive", "unaffordable"}
        economic_ok = cost_ok and (
            bool(candidate.economic_viability_notes.strip())
            or candidate.development_complexity.lower() != "impossible"
        )
        gate8_fail = "" if economic_ok else EvidenceAggregator.classify_gate_failure(GATE_NAMES[7], candidate, problem, gap)
        gates.append(
            QualityGate(
                name=GATE_NAMES[7],
                description="Deployment cost is realistic with zero mandatory paid subscription APIs.",
                status=QualityGateStatus.PASSED if economic_ok else QualityGateStatus.FAILED,
                justification=(
                    f"Cost profile: {candidate.estimated_cost}; "
                    f"Economic notes: {candidate.economic_viability_notes[:100] if candidate.economic_viability_notes else 'Standard open-source stack.'}"
                    + (f" [{gate8_fail}]" if gate8_fail else "")
                ),
            )
        )

        # Gate 9: Hackathon Buildability and Demonstration
        deadline_ok = bool(
            candidate.estimated_hours is not None
            and candidate.estimated_hours <= hours * 1.15
            and hours > 0
            and candidate.hackathon_demo_plan.strip()
        )
        gate9_fail = "" if deadline_ok else EvidenceAggregator.classify_gate_failure(GATE_NAMES[8], candidate, problem, gap)
        gates.append(
            QualityGate(
                name=GATE_NAMES[8],
                description="The build fits the available hackathon time and has a concrete demo plan.",
                status=QualityGateStatus.PASSED if deadline_ok else QualityGateStatus.FAILED,
                justification=(
                    f"Estimated {candidate.estimated_hours or 0:.0f}h vs {hours:.1f}h available; "
                    f"Demo plan: {'Documented' if candidate.hackathon_demo_plan.strip() else 'Missing'}."
                    + (f" [{gate9_fail}]" if gate9_fail else "")
                ),
            )
        )

        # Gate 10: Risk, Ethics and Sustainability
        mitigated_risks = [r for r in candidate.risks if r.mitigation]
        risk_ok = (
            len(candidate.risks) >= 2
            and len(candidate.disadvantages) >= 1
            and len(candidate.mitigation_strategies) >= 1
            and len(mitigated_risks) >= 1
        )
        gate10_fail = "" if risk_ok else EvidenceAggregator.classify_gate_failure(GATE_NAMES[9], candidate, problem, gap)
        gates.append(
            QualityGate(
                name=GATE_NAMES[9],
                description="Risks, disadvantages, ethical implications, and mitigations are documented.",
                status=QualityGateStatus.PASSED if risk_ok else QualityGateStatus.FAILED,
                justification=(
                    f"{len(candidate.risks)} risk(s), {len(candidate.disadvantages)} "
                    f"disadvantage(s), {len(candidate.mitigation_strategies)} "
                    f"mitigation(s), {len(mitigated_risks)} mitigated risk(s)."
                    + (f" [{gate10_fail}]" if gate10_fail else "")
                ),
            )
        )

        return gates
