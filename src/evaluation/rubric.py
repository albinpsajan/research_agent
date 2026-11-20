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
from src.utils.hackathon_time import available_hours, deadline_note

logger = get_logger("evaluation.rubric")

GATE_NAMES = (
    "Credible evidence of the problem",
    "Existing-solution investigation",
    "Honest originality classification",
    "Practical implementation path",
    "Realistic hackathon deadline",
    "Risk and disadvantage assessment",
    "Compliance with hackathon rules",
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
        "evidence": "Credible evidence of the problem",
        "existing": "Existing-solution investigation",
        "solution investigation": "Existing-solution investigation",
        "originality": "Honest originality classification",
        "implementation": "Practical implementation path",
        "practical": "Practical implementation path",
        "deadline": "Realistic hackathon deadline",
        "time": "Realistic hackathon deadline",
        "risk": "Risk and disadvantage assessment",
        "disadvantage": "Risk and disadvantage assessment",
        "compliance": "Compliance with hackathon rules",
        "rules": "Compliance with hackathon rules",
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
        prompt = self._prompt(candidate, problem, gap, hackathon, intelligence, hours)
        result = self.llm.generate_json(prompt, EvaluationLLM, SYSTEM)

        by_criterion: dict[str, CriterionScoreLLM] = {}
        for item in result.scores:
            matched = _match_criterion(item.name, weights)
            if matched and matched not in by_criterion:
                by_criterion[matched] = item

        scores: list[ScoreCriterion] = []
        for criterion, weight in weights.items():
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

Return all eight rubric criteria exactly once, all seven gates, an overall
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

        evidence = problem.evidence if problem else []
        urls = {e.source_url for e in evidence if e.source_url}
        max_credibility = max((e.credibility for e in evidence), default=0.0)
        credible = len(urls) >= 2 and max_credibility >= 0.6
        gates.append(
            QualityGate(
                name=GATE_NAMES[0],
                description="At least two independent, credible sources support the problem.",
                status=QualityGateStatus.PASSED
                if credible
                else QualityGateStatus.FAILED,
                justification=(
                    f"{len(urls)} distinct evidence URL(s); highest credibility "
                    f"{max_credibility:.2f}."
                ),
                evidence=sorted(urls)[:8],
            )
        )

        existing_count = (
            len(gap.existing_solutions) + len(gap.github_projects) if gap else 0
        )
        investigated = bool(
            gap
            and gap.classification != OpportunityClassification.INSUFFICIENT_EVIDENCE
            and existing_count > 0
            and gap.evidence_summary.strip()
        )
        gates.append(
            QualityGate(
                name=GATE_NAMES[1],
                description="Real existing solutions or repositories were investigated.",
                status=QualityGateStatus.PASSED
                if investigated
                else QualityGateStatus.FAILED,
                justification=(
                    f"{existing_count} existing solution/repository record(s); "
                    f"classification={gap.classification.value if gap else 'none'}."
                ),
                evidence=(
                    [s.url for s in gap.existing_solutions if s.url][:8] if gap else []
                ),
            )
        )

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
        gates.append(
            QualityGate(
                name=GATE_NAMES[2],
                description="Originality is classified honestly and differentiation is stated.",
                status=QualityGateStatus.PASSED
                if originality_ok
                else QualityGateStatus.FAILED,
                justification=(
                    f"Classification: {gap.classification.value if gap else 'none'}; "
                    f"differentiation length: {len(candidate.unique_differentiation)} chars."
                ),
                evidence=[gap.differentiation_potential]
                if gap and gap.differentiation_potential
                else [],
            )
        )

        unavailable = [
            req.description
            for req in candidate.data_requirements + candidate.api_requirements
            if req.availability == "unavailable"
        ]
        practical = bool(
            candidate.proposed_solution.strip()
            and candidate.technical_architecture.strip()
            and candidate.estimated_hours > 0
            and not unavailable
        )
        gates.append(
            QualityGate(
                name=GATE_NAMES[3],
                description="A concrete architecture and available data/API path exist.",
                status=QualityGateStatus.PASSED
                if practical
                else QualityGateStatus.FAILED,
                justification=(
                    "Solution and architecture are specified."
                    if practical
                    else f"Missing architecture/solution or unavailable dependencies: {unavailable[:4]}"
                ),
            )
        )

        deadline_ok = candidate.estimated_hours <= hours * 1.15 and hours > 0
        gates.append(
            QualityGate(
                name=GATE_NAMES[4],
                description="The build fits the available hackathon time.",
                status=QualityGateStatus.PASSED
                if deadline_ok
                else QualityGateStatus.FAILED,
                justification=(
                    f"Estimated {candidate.estimated_hours:.0f}h vs {hours:.1f}h available. "
                    f"{deadline_note(hackathon)}"
                ),
            )
        )

        mitigated_risks = [r for r in candidate.risks if r.mitigation]
        risk_ok = (
            len(candidate.risks) >= 2
            and len(candidate.disadvantages) >= 1
            and len(candidate.mitigation_strategies) >= 1
            and len(mitigated_risks) >= 1
        )
        gates.append(
            QualityGate(
                name=GATE_NAMES[5],
                description="Risks, disadvantages and mitigations are documented.",
                status=QualityGateStatus.PASSED
                if risk_ok
                else QualityGateStatus.FAILED,
                justification=(
                    f"{len(candidate.risks)} risk(s), {len(candidate.disadvantages)} "
                    f"disadvantage(s), {len(candidate.mitigation_strategies)} "
                    f"mitigation(s), {len(mitigated_risks)} mitigated risk(s)."
                ),
            )
        )

        restrictions = intelligence.technical_restrictions + (
            [hackathon.constraints] if hackathon.constraints else []
        )
        # The independent evaluator supplies the judgement for rules; the
        # deterministic layer records whether rules were available at all.
        gates.append(
            QualityGate(
                name=GATE_NAMES[6],
                description="The solution does not violate supplied hackathon rules.",
                status=QualityGateStatus.PASSED,
                justification=(
                    "No explicit rules were supplied; compliance is checked against "
                    "the stated constraints only."
                    if not restrictions
                    else "Checked against supplied constraints: "
                    + "; ".join(restrictions[:4])
                ),
            )
        )
        return gates
