"""Agent 4 — Solution Architect and Feasibility Analyst."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from config.logging_config import get_logger
from src.agents.base import BaseAgent
from src.models.candidate import (
    CandidateSolution,
    FeasibilityReport,
    RiskAssessment,
    TechnicalRequirement,
)
from src.models.domain import ProblemCandidate
from src.models.hackathon import HackathonInput, HackathonIntelligence
from src.models.research import InnovationGap, OpportunityClassification
from src.knowledge.hackathon_playbook import HackathonPlaybookService
from src.knowledge.document_intelligence.service import DocumentIntelligenceService
from src.research.evidence_aggregator import EvidenceAggregator

logger = get_logger("agents.solution_architect")

SYSTEM = """You are the Solution Architect and Feasibility Analyst for HackathonIQ.
You design solutions that can actually be built and demonstrated inside a
hackathon, not impressive slideware.
Rules:
- Ground the solution in the problem evidence and the investigated gap.
- Be explicit about data, APIs, infrastructure, cost and dependencies.
- Estimate hours honestly, including integration, testing and demo preparation.
- Identify real risks and concrete mitigations.
- If disadvantages outweigh benefits, recommend rejection rather than forcing a
  weak idea. Never invent APIs, datasets, papers or URLs. Return JSON only.
"""


class RequirementLLM(BaseModel):
    category: str = "data"
    description: str
    availability: str = "unknown"
    cost: str = "free"
    risk_level: str = "low"


class RiskLLM(BaseModel):
    risk_type: str = "technical"
    description: str
    severity: str = "medium"
    likelihood: str = "possible"
    mitigation: str = ""


class SolutionLLM(BaseModel):
    title: str
    proposed_solution: str
    target_users: list[str] = Field(default_factory=list)
    user_pain_point: str = ""
    unique_differentiation: str = ""
    relevant_technologies: list[str] = Field(default_factory=list)
    data_requirements: list[RequirementLLM] = Field(default_factory=list)
    api_requirements: list[RequirementLLM] = Field(default_factory=list)
    technical_architecture: str = ""
    development_complexity: str = "medium"
    estimated_hours: float = Field(default=24, ge=0, le=2000)
    infrastructure_requirements: list[str] = Field(default_factory=list)
    estimated_cost: str = "minimal"
    dependencies: list[str] = Field(default_factory=list)
    risks: list[RiskLLM] = Field(default_factory=list)
    advantages: list[str] = Field(default_factory=list)
    disadvantages: list[str] = Field(default_factory=list)
    mitigation_strategies: list[str] = Field(default_factory=list)
    hackathon_demo_plan: str = ""
    should_reject: bool = False
    rejection_reason: str = ""
    feasibility_confidence: float = Field(default=0.5, ge=0, le=1)

    @field_validator("feasibility_confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: Any) -> Any:
        if isinstance(v, (int, float)) and v > 1:
            return min(1.0, v / 100.0)
        return v


_COMPLEXITY_SCORE = {"low": 0.95, "medium": 0.72, "high": 0.45, "very_high": 0.2}
_CLASSIFICATION_SCORE = {
    OpportunityClassification.DIFFERENTIATED: 4.0,
    OpportunityClassification.UNDERSERVED: 3.0,
    OpportunityClassification.LIMITED_SOLUTION: 2.0,
    OpportunityClassification.PARTIALLY_SOLVED: 1.0,
    OpportunityClassification.COMMONLY_SOLVED: 0.0,
    OpportunityClassification.INSUFFICIENT_EVIDENCE: 0.0,
}
_SERIOUSNESS_SCORE = {"critical": 4.0, "high": 3.0, "moderate": 2.0, "low": 1.0}


class SolutionArchitectAgent(BaseAgent):
    """Shortlists candidates across domains and produces feasibility reports."""

    name = "solution_architect"
    description = "Turns problems into realistic, differentiated solution candidates"

    def run(
        self,
        session_id: str,
        problems: list[ProblemCandidate],
        gaps: list[InnovationGap],
        hackathon: HackathonInput,
        intelligence: HackathonIntelligence,
        *,
        max_finalists: int | None = None,
        intelligence_context: str = "",
    ) -> FeasibilityReport:
        finalist_limit = max_finalists or self.settings.max_finalists
        gap_by_problem = {gap.problem_candidate_id: gap for gap in gaps}
        shortlisted = self._shortlist(problems, gap_by_problem, finalist_limit)
        available_hours = self._available_hours(hackathon)
        report = FeasibilityReport()

        for index, problem in enumerate(shortlisted, start=1):
            gap = gap_by_problem.get(problem.id or "")
            solution = self._architect(
                session_id=session_id,
                problem=problem,
                gap=gap,
                intelligence=intelligence,
                available_hours=available_hours,
                intelligence_context=intelligence_context,
                theme=hackathon.theme,
            )
            solution.id = f"C{index:02d}"
            solution.domain = problem.domain
            solution.problem_candidate_id = problem.id or ""
            solution.feasibility_score = self._feasibility(solution, available_hours)
            if not solution.title:
                solution.title = problem.title

            if solution.is_rejected:
                report.rejected_candidates.append(solution)
            else:
                report.candidates.append(solution)
            self.repository.save_candidate_solution(
                session_id, solution.model_dump(mode="json")
            )

        report.total_evaluated = len(shortlisted)
        self._save(session_id, "feasibility_report", report)
        return report

    # ------------------------------------------------------------------
    # Shortlisting is deterministic and cross-domain.
    # ------------------------------------------------------------------

    @staticmethod
    def _shortlist(
        problems: list[ProblemCandidate],
        gaps: dict[str, InnovationGap],
        limit: int,
    ) -> list[ProblemCandidate]:
        def score(problem: ProblemCandidate) -> float:
            gap = gaps.get(problem.id or "")
            classification = (
                _CLASSIFICATION_SCORE.get(gap.classification, 0.0) if gap else 0.0
            )
            evidence = min(len(problem.evidence), 4) * 1.2
            significance = _SERIOUSNESS_SCORE.get(problem.seriousness, 1.0)
            confidence = problem.confidence * 3
            github = min(len(gap.github_projects), 5) * 0.2 if gap else 0
            penalty = 6 if problem.is_generic else 0
            return (
                significance + evidence + classification + confidence + github - penalty
            )

        ordered = sorted(problems, key=score, reverse=True)
        selected: list[ProblemCandidate] = []
        domain_counts: dict[str, int] = {}
        # First pass: at most two per domain to force cross-domain competition.
        for problem in ordered:
            if domain_counts.get(problem.domain, 0) >= 2:
                continue
            selected.append(problem)
            domain_counts[problem.domain] = domain_counts.get(problem.domain, 0) + 1
            if len(selected) >= limit:
                return selected
        for problem in ordered:
            if problem not in selected:
                selected.append(problem)
                if len(selected) >= limit:
                    break
        return selected

    # ------------------------------------------------------------------
    # One architecture call per finalist.
    # ------------------------------------------------------------------

    def _architect(
        self,
        *,
        session_id: str,
        problem: ProblemCandidate,
        gap: InnovationGap | None,
        intelligence: HackathonIntelligence,
        available_hours: float,
        intelligence_context: str,
        theme: str,
    ) -> CandidateSolution:
        evidence_text = (
            "\n".join(
                f"- {e.description} | {e.source_url or 'no URL'} | credibility={e.credibility:.2f}"
                for e in problem.evidence[:6]
            )
            or "- No direct evidence was retrieved."
        )
        existing_text = ""
        if gap:
            existing_text = "\n".join(
                f"- {s.name} ({s.solution_type}): {s.description[:300]} | "
                f"limitations: {', '.join(s.disadvantages[:3]) or 'not documented'}"
                for s in gap.existing_solutions[:6]
            )
            github_text = "\n".join(
                f"- {p.name}: {p.stars} stars, {p.language or 'unknown language'}, "
                f"active={p.is_active}, {p.description or ''}"
                for p in gap.github_projects[:6]
            )
        else:
            github_text = "(no repository research available)"
        if not existing_text:
            existing_text = "(no existing solutions were verifiably identified)"

        playbook = HackathonPlaybookService()
        playbook_entries = playbook.retrieve_for_solution_architect(problem.domain, hours=available_hours)
        playbook_guidance = playbook.format_guidance_for_prompt(playbook_entries)

        doc_service = DocumentIntelligenceService(self.repository, self.llm)
        doc_hits = doc_service.search_evidence(
            query=f"{problem.title} {problem.domain} architecture datasets API implementation feasibility",
            session_id=session_id,
            limit=4,
        )
        doc_context = "\n".join(h.as_evidence_context(i) for i, h in enumerate(doc_hits, 1))

        prompt = f"""Hackathon theme: {theme}
Problem domain: {problem.domain} / {problem.subdomain or "general"}
Problem candidate: {problem.title}
Problem: {problem.description}
Affected people: {problem.affected_people}
Seriousness: {problem.seriousness}
Evidence:
{evidence_text}
Inadequate current solutions: {problem.inadequate_solutions}
Overlooked needs: {problem.overlooked_needs}

{playbook_guidance}

UPLOADED TECHNICAL SPECS & DATASET REFERENCES:
{doc_context or "(none uploaded)"}

Opportunity: {problem.emerging_opportunities}
Existing solutions found:
{existing_text}
Real GitHub projects:
{github_text}
Innovation classification: {gap.classification.value if gap else "unknown"}
Gap: {gap.gap_description if gap else "unknown"}
Differentiation potential: {gap.differentiation_potential if gap else "unknown"}
Organiser goals: {intelligence.organizer_goals[:6]}
Technical restrictions: {intelligence.technical_restrictions[:6]}
Time available: {available_hours:.1f} hours
Recent intelligence: {intelligence_context[:1200] or "(none)"}

Design ONE refined hackathon solution. It must:
- solve a specific, evidence-backed problem for named users;
- provide explicit unique_differentiation from the existing solutions above (at least 30 characters);
- specify concrete open-source relevant_technologies (frameworks, models, libraries);
- define a concrete technical_architecture (data ingestion, analytics engine, and interface layers);
- document at least 2 concrete technical/practical risks with clear mitigations;
- document at least 1 disadvantage and mitigation strategy;
- be buildable and demonstrable within {available_hours:.1f} hours by a small team;
- use realistic free/low-cost data and APIs;
- include a concrete demo plan.
If the disadvantages genuinely outweigh the benefits or the time is unrealistic,
set should_reject=true and explain why. Do not force a weak candidate."""
        result = self.llm.generate_json(prompt, SolutionLLM, SYSTEM)

        complexity = (
            result.development_complexity
            if result.development_complexity in _COMPLEXITY_SCORE
            else "medium"
        )
        solution = CandidateSolution(
            title=result.title.strip()[:220],
            problem_candidate_id=problem.id or "",
            problem_statement=problem.description,
            target_users=result.target_users[:8],
            user_pain_point=result.user_pain_point,
            supporting_evidence=[e.description for e in problem.evidence[:6]],
            existing_alternatives=[
                s.name for s in (gap.existing_solutions if gap else [])
            ][:8],
            identified_gap=gap.gap_description if gap else "",
            proposed_solution=result.proposed_solution,
            unique_differentiation=result.unique_differentiation,
            relevant_technologies=result.relevant_technologies[:12],
            data_requirements=[
                TechnicalRequirement(
                    category=r.category,
                    description=r.description,
                    availability=r.availability,
                    cost=r.cost,
                    risk_level=r.risk_level,
                )
                for r in result.data_requirements[:10]
            ],
            api_requirements=[
                TechnicalRequirement(
                    category=r.category,
                    description=r.description,
                    availability=r.availability,
                    cost=r.cost,
                    risk_level=r.risk_level,
                )
                for r in result.api_requirements[:10]
            ],
            technical_architecture=result.technical_architecture,
            development_complexity=complexity,
            estimated_hours=result.estimated_hours,
            infrastructure_requirements=result.infrastructure_requirements[:8],
            estimated_cost=result.estimated_cost,
            dependencies=result.dependencies[:10],
            risks=[
                RiskAssessment(
                    risk_type=r.risk_type,
                    description=r.description,
                    severity=r.severity
                    if r.severity in {"low", "medium", "high", "critical"}
                    else "medium",
                    likelihood=r.likelihood
                    if r.likelihood in {"unlikely", "possible", "likely", "certain"}
                    else "possible",
                    mitigation=r.mitigation or None,
                )
                for r in result.risks[:10]
            ],
            advantages=result.advantages[:8],
            disadvantages=result.disadvantages[:8],
            mitigation_strategies=result.mitigation_strategies[:8],
            hackathon_demo_plan=result.hackathon_demo_plan,
            is_rejected=result.should_reject,
            rejection_reason=result.rejection_reason or None,
            domain=problem.domain,
            confidence=result.feasibility_confidence,
        )
        # Ensure complete research evidence, technology stack, and differentiation are attached
        EvidenceAggregator.enrich_candidate_solution(solution, problem, gap, theme=theme)
        return solution

    # ------------------------------------------------------------------
    # Feasibility and time accounting
    # ------------------------------------------------------------------

    @staticmethod
    def _available_hours(hackathon: HackathonInput) -> float:
        from src.utils.hackathon_time import available_hours

        return available_hours(hackathon)

    @staticmethod
    def _feasibility(solution: CandidateSolution, available_hours: float) -> float:
        complexity = _COMPLEXITY_SCORE.get(solution.development_complexity, 0.5)
        if available_hours <= 0:
            time_fit = 0.0
        elif solution.estimated_hours <= available_hours * 0.7:
            time_fit = 1.0
        elif solution.estimated_hours <= available_hours:
            time_fit = 0.7
        elif solution.estimated_hours <= available_hours * 1.3:
            time_fit = 0.3
        else:
            time_fit = 0.0
        score = 0.45 * complexity + 0.30 * time_fit + 0.25 * solution.confidence
        return round(max(0.0, min(score, 1.0)), 3)
