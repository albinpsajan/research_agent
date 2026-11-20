"""Agent 5 — Adversarial Critic and Independent Final Evaluator.

Runs bounded evidence-backed debate rounds, applies justified score
adjustments, ranks candidates and independently selects one winner — or
honestly rejects every candidate.
"""

from __future__ import annotations

import json
import random
import re

from pydantic import BaseModel, Field

from config.logging_config import get_logger
from src.agents.base import BaseAgent, evidence_lines
from src.evaluation.rubric import EvaluationService
from src.models.candidate import CandidateSolution
from src.models.domain import ProblemCandidate
from src.models.evaluation import (
    CandidateEvaluation,
    DebateHistory,
    DebateRound,
    FinalEvaluationReport,
    WinnerSelection,
)
from src.models.hackathon import HackathonInput, HackathonIntelligence
from src.models.research import InnovationGap
from src.research.base import SearchResult
from src.research.registry import SearchBundle

logger = get_logger("agents.adversarial_critic")

SYSTEM = """You are the Adversarial Critic and Independent Final Evaluator for
HackathonIQ. You are paid to find weaknesses, not to agree with the architects.
Challenge importance, theme relevance, originality, evidence, feasibility, demo
quality and organiser fit. Require evidence. If a criticism cannot be answered,
the candidate must be downgraded or rejected. You may reject every candidate.
Never invent facts, URLs, competitors or statistics. Return JSON only.
"""


class CriticismLLM(BaseModel):
    issue: str
    category: str = "originality"
    severity: str = "major"
    why_it_matters: str = ""
    evidence_needed: str = ""
    evidence_query: str = ""


class CritiqueLLM(BaseModel):
    criticisms: list[CriticismLLM] = Field(default_factory=list, max_length=6)
    generic_risk: str = ""
    verdict: str = "mixed"
    summary: str = ""


class RebuttalItemLLM(BaseModel):
    issue: str
    response: str
    evidence_indices: list[int] = Field(default_factory=list, max_length=5)
    resolved: bool = False
    residual_risk: str = ""


class RebuttalLLM(BaseModel):
    rebuttals: list[RebuttalItemLLM] = Field(default_factory=list)
    revised_differentiation: str = ""
    new_risks: list[str] = Field(default_factory=list)
    recommendation: str = "advance"


class VerdictLLM(BaseModel):
    resolved_count: int = 0
    unresolved_critical: int = 0
    score_adjustment: float = Field(default=0, ge=-20, le=5)
    recommendation: str = "advance"
    summary: str = ""
    evidence_quality: str = ""


class SelectionLLM(BaseModel):
    winner_label: str = ""
    runner_up_labels: list[str] = Field(default_factory=list)
    reject_all: bool = False
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)


class AdversarialCriticAgent(BaseAgent):
    """Challenges finalists and performs the independent final selection."""

    name = "adversarial_critic"
    description = "Challenges every finalist and independently selects the winner"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.evaluator = EvaluationService(self.llm)

    def run(
        self,
        session_id: str,
        candidates: list[CandidateSolution],
        problems: list[ProblemCandidate],
        gaps: list[InnovationGap],
        hackathon: HackathonInput,
        intelligence: HackathonIntelligence,
        *,
        max_rounds: int | None = None,
    ) -> FinalEvaluationReport:
        problem_by_id = {p.id: p for p in problems}
        gap_by_problem = {g.problem_candidate_id: g for g in gaps}
        rounds_limit = max_rounds or self.settings.max_debate_rounds
        evaluations: list[CandidateEvaluation] = []
        debates: list[DebateHistory] = []

        for candidate in candidates:
            problem = problem_by_id.get(candidate.problem_candidate_id)
            gap = gap_by_problem.get(candidate.problem_candidate_id)
            evaluation = self.evaluator.evaluate(
                candidate, problem, gap, hackathon, intelligence
            )
            debate = self._debate(
                session_id, candidate, problem, gap, evaluation, rounds_limit
            )
            evaluation.debate_adjustment = (
                debate.score_after_debate - debate.score_before_debate
            )
            evaluation.debate_recommendation = debate.recommendation
            evaluation.calculate_total()
            self.repository.save_evaluation(
                session_id=session_id,
                candidate_id=candidate.id or "",
                total_score=evaluation.total_score,
                all_gates_passed=evaluation.all_gates_passed,
                is_qualified=evaluation.is_qualified,
                rank=None,
                scores_json=json.dumps([s.model_dump() for s in evaluation.scores]),
                gates_json=json.dumps(
                    [g.model_dump() for g in evaluation.quality_gates]
                ),
                assessment=evaluation.overall_assessment,
            )
            evaluations.append(evaluation)
            debates.append(debate)

        qualified = [e for e in evaluations if e.is_qualified]
        qualified.sort(key=lambda e: e.total_score, reverse=True)
        for rank, evaluation in enumerate(qualified, start=1):
            evaluation.rank = rank

        winner = self._select(
            session_id=session_id,
            evaluations=evaluations,
            candidates=candidates,
            problems=problems,
            gaps=gaps,
            intelligence=intelligence,
        )
        winner.debate_summary = "\n".join(
            f"{d.candidate_id}: {d.recommendation}; adjustment {d.score_after_debate - d.score_before_debate:+.1f}; "
            f"{d.final_assessment[:200]}"
            for d in debates
        )
        winner.total_candidates_evaluated = len(evaluations)
        winner.total_candidates_rejected = sum(
            1 for e in evaluations if not e.is_qualified
        )
        report = FinalEvaluationReport(
            evaluations=evaluations,
            debates=debates,
            winner=winner,
            scoring_methodology=(
                "Agreed 100-point weighted rubric with seven mandatory quality "
                "gates. Deterministic checks can veto gates. Bounded adversarial "
                "debate produces a justified score adjustment. The final selection "
                "is made by the independent critic over anonymised finalists and is "
                "guarded by qualification gates and a 60/100 minimum."
            ),
        )
        self._save(session_id, "final_evaluation", report)
        return report

    # ------------------------------------------------------------------
    # Debate
    # ------------------------------------------------------------------

    def _debate(
        self,
        session_id: str,
        candidate: CandidateSolution,
        problem: ProblemCandidate | None,
        gap: InnovationGap | None,
        evaluation: CandidateEvaluation,
        max_rounds: int,
    ) -> DebateHistory:
        debate = DebateHistory(
            candidate_id=candidate.id or "",
            score_before_debate=evaluation.total_score,
            score_after_debate=evaluation.total_score,
            recommendation="advance",
        )
        bundle = self._evidence_bundle(problem, gap)
        prior: list[str] = []

        for round_number in range(1, max_rounds + 1):
            critique = self._critique(candidate, problem, gap, evaluation, prior)
            if not critique.criticisms:
                debate.final_assessment = "No material criticisms were raised."
                debate.recommendation = "advance"
                break

            # Retrieve targeted evidence requested by the critic.
            for criticism in critique.criticisms[:2]:
                if criticism.evidence_query.strip():
                    extra = self.research.search(
                        session_id,
                        criticism.evidence_query,
                        source_types=["openalex", "crossref", "arxiv", "github", "rss"],
                        limit=3,
                    )
                    bundle.extend(extra)
            bundle.dedupe()

            rebuttal = self._rebuttal(candidate, critique, bundle)
            verdict = self._verdict(critique, rebuttal)

            resolved = verdict.unresolved_critical == 0
            debate.rounds.append(
                DebateRound(
                    round_number=round_number,
                    candidate_id=candidate.id or "",
                    criticism="\n".join(
                        f"[{c.severity}/{c.category}] {c.issue} — {c.why_it_matters}"
                        for c in critique.criticisms
                    ),
                    rebuttal="\n".join(
                        f"{r.issue}: {r.response} (resolved={r.resolved})"
                        for r in rebuttal.rebuttals
                    ),
                    evidence_provided=[
                        bundle.results[i - 1].url
                        for r in rebuttal.rebuttals
                        for i in r.evidence_indices
                        if 1 <= i <= len(bundle.results) and bundle.results[i - 1].url
                    ][:8],
                    criticism_resolved=resolved,
                    score_adjustment=verdict.score_adjustment,
                    notes=verdict.summary,
                )
            )
            self.repository.save_debate_round(
                session_id=session_id,
                candidate_id=candidate.id or "",
                round_number=round_number,
                criticism=debate.rounds[-1].criticism,
                rebuttal=debate.rounds[-1].rebuttal,
                evidence=debate.rounds[-1].evidence_provided,
                resolved=resolved,
                score_adjustment=verdict.score_adjustment,
            )
            prior.extend(
                f"Round {round_number}: {c.issue} -> resolved={resolved}"
                for c in critique.criticisms
            )
            if rebuttal.revised_differentiation:
                candidate.unique_differentiation = (
                    candidate.unique_differentiation
                    + " Revised after criticism: "
                    + rebuttal.revised_differentiation
                )[:2000]
            for risk in rebuttal.new_risks[:3]:
                if risk and risk not in candidate.disadvantages:
                    candidate.disadvantages.append(risk)

            if verdict.recommendation == "reject":
                debate.recommendation = "reject"
                debate.final_assessment = verdict.summary
                break
            if resolved:
                debate.recommendation = (
                    "downgrade" if verdict.score_adjustment < 0 else "advance"
                )
                debate.final_assessment = verdict.summary
                break
            debate.recommendation = "downgrade"
            debate.final_assessment = verdict.summary

        total_adjustment = sum(r.score_adjustment for r in debate.rounds)
        debate.score_after_debate = round(
            max(0.0, min(100.0, debate.score_before_debate + total_adjustment)), 2
        )
        return debate

    def _critique(
        self,
        candidate: CandidateSolution,
        problem: ProblemCandidate | None,
        gap: InnovationGap | None,
        evaluation: CandidateEvaluation,
        prior: list[str],
    ) -> CritiqueLLM:
        prompt = f"""Candidate: {candidate.title}
Domain: {candidate.domain}
Problem: {candidate.problem_statement}
Affected users: {candidate.target_users}
Proposed solution: {candidate.proposed_solution}
Differentiation: {candidate.unique_differentiation}
Evidence: {candidate.supporting_evidence}
Existing alternatives: {candidate.existing_alternatives}
Gap: {candidate.identified_gap}
Estimated hours: {candidate.estimated_hours}
Risks: {[r.description for r in candidate.risks]}
Disadvantages: {candidate.disadvantages}
Demo plan: {candidate.hackathon_demo_plan}
Current score: {evaluation.total_score}/100
Gate failures: {[g.name for g in evaluation.quality_gates if g.status.value != "passed"]}
Prior debate: {prior or "none"}

Act as a hostile but fair hackathon judge. Challenge at least:
- Is this important and genuinely relevant to the theme?
- Would an ordinary chatbot suggest this? Are there hundreds of similar projects?
- Is the differentiation evidenced, or just claimed?
- Why has this not been solved already?
- Is the technical approach and timeline realistic?
- What would judges attack in the demo?
- Are assumptions unsupported? Could another domain offer more?
- Is a competing finalist objectively stronger?

Return up to 5 specific criticisms. For each, give an evidence query that could
help answer it. Do not repeat issues already resolved in prior rounds."""
        return self.llm.generate_json(prompt, CritiqueLLM, SYSTEM)

    def _rebuttal(
        self,
        candidate: CandidateSolution,
        critique: CritiqueLLM,
        bundle: SearchBundle,
    ) -> RebuttalLLM:
        issues = "\n".join(
            f"{i}. [{c.severity}] {c.issue}\nWhy: {c.why_it_matters}\n"
            f"Evidence needed: {c.evidence_needed}"
            for i, c in enumerate(critique.criticisms, start=1)
        )
        prompt = f"""Candidate: {candidate.title}
Solution: {candidate.proposed_solution}
Differentiation: {candidate.unique_differentiation}
Evidence:
{evidence_lines(bundle, max_items=20)}

CRITICISMS:
{issues}

Respond to every criticism with evidence. Cite evidence indices from the list
above. If the evidence does not support the candidate, mark resolved=false and
state the residual risk honestly. Do not invent evidence. If the criticism
invalidates the idea, recommend "reject". Otherwise revise the differentiation
where the evidence supports a sharper claim and list any newly discovered risks."""
        return self.llm.generate_json(prompt, RebuttalLLM, SYSTEM)

    def _verdict(self, critique: CritiqueLLM, rebuttal: RebuttalLLM) -> VerdictLLM:
        resolved = sum(1 for r in rebuttal.rebuttals if r.resolved)
        critical = sum(
            1
            for c in critique.criticisms
            if c.severity == "critical"
            and not any(
                r.issue.strip().lower() == c.issue.strip().lower() and r.resolved
                for r in rebuttal.rebuttals
            )
        )
        prompt = f"""Criticisms:
{[c.model_dump() for c in critique.criticisms]}
Rebuttals:
{[r.model_dump() for r in rebuttal.rebuttals]}
Architect recommendation: {rebuttal.recommendation}
Computed status: resolved criticisms count={resolved}, unresolved critical count={critical}

Adjudicate independently. Did the evidence actually answer each material
criticism? Count resolved items and unresolved critical items. Apply a score
adjustment between -20 and +5: negative when material criticism survives,
zero when resolved without changing quality, small positive only when new
evidence materially strengthens the candidate. Recommend advance, downgrade or
reject."""
        verdict = self.llm.generate_json(prompt, VerdictLLM, SYSTEM)
        verdict.unresolved_critical = max(verdict.unresolved_critical, critical)
        if verdict.unresolved_critical > 0 and verdict.score_adjustment > 0:
            verdict.score_adjustment = 0
        if rebuttal.recommendation == "reject" and verdict.recommendation != "reject":
            verdict.recommendation = "downgrade"
        return verdict

    # ------------------------------------------------------------------
    # Final independent selection
    # ------------------------------------------------------------------

    def _select(
        self,
        *,
        session_id: str,
        evaluations: list[CandidateEvaluation],
        candidates: list[CandidateSolution],
        problems: list[ProblemCandidate],
        gaps: list[InnovationGap],
        intelligence: HackathonIntelligence,
    ) -> WinnerSelection:
        qualified = [e for e in evaluations if e.is_qualified]
        if not qualified:
            return WinnerSelection(
                has_winner=False,
                rejection_reason=(
                    "No candidate passed every mandatory quality gate after "
                    "adversarial debate. HackathonIQ will not manufacture a winner."
                ),
                selection_methodology="All candidates failed one or more mandatory gates.",
                runner_ups=[],
            )

        candidate_by_id = {c.id: c for c in candidates}
        problem_by_id = {p.id: p for p in problems}
        gap_by_problem = {g.problem_candidate_id: g for g in gaps}
        ordered = sorted(qualified, key=lambda e: e.total_score, reverse=True)
        rng = random.Random(session_id)
        rng.shuffle(ordered)
        labels = "ABCDEFGHIJ"
        label_map = {
            labels[index]: evaluation for index, evaluation in enumerate(ordered)
        }

        summaries = []
        for label, evaluation in label_map.items():
            candidate = candidate_by_id.get(evaluation.candidate_id)
            if not candidate:
                continue
            problem = problem_by_id.get(candidate.problem_candidate_id)
            gap = gap_by_problem.get(candidate.problem_candidate_id)
            summaries.append(
                f"""FINALIST {label}
Domain: {candidate.domain}
Problem: {problem.title if problem else candidate.problem_statement[:150]}
Solution: {candidate.proposed_solution[:700]}
Differentiation: {candidate.unique_differentiation[:600]}
Evidence count: {len(problem.evidence) if problem else 0}
Existing-solution classification: {gap.classification.value if gap else "unknown"}
Gap: {gap.gap_description[:400] if gap else ""}
Rubric score after debate: {evaluation.total_score}/100
Gates: {"all passed" if evaluation.all_gates_passed else [g.name for g in evaluation.quality_gates if g.status.value != "passed"]}
Strengths: {evaluation.strengths[:4]}
Weaknesses: {evaluation.weaknesses[:4]}
Debate recommendation: {evaluation.debate_recommendation}
"""
            )
        prompt = f"""Organiser goals: {intelligence.organizer_goals[:6]}
Recurring priorities: {intelligence.recurring_priorities[:6]}

{chr(10).join(summaries)}

Select ONE strongest evidence-backed problem statement and solution. The score
is evidence, not a decision. Compare across domains. Choose the candidate most
likely to win THIS hackathon on problem significance, originality, feasibility,
organiser fit and demo impact. You may reject all candidates if none deserves to
win. Do not select a candidate whose gates failed. Return the finalist label
exactly (A-J), runner-up labels, reject_all and a rationale that references the
comparison."""
        result = self.llm.generate_json(prompt, SelectionLLM, SYSTEM)

        if result.reject_all:
            return WinnerSelection(
                has_winner=False,
                rejection_reason=result.rationale
                or "The independent critic rejected all candidates.",
                selection_methodology="Independent critic selection over anonymised qualified finalists.",
                runner_ups=[],
            )

        label = _label(result.winner_label)
        chosen = label_map.get(label)
        if chosen is None or not chosen.is_qualified or chosen.total_score < 60:
            return WinnerSelection(
                has_winner=False,
                rejection_reason=(
                    "The independent critic selected a candidate that did not meet "
                    "the mandatory gates or the 60/100 minimum. No winner is "
                    "declared rather than overriding the quality controls."
                ),
                selection_methodology="Independent critic selection with deterministic qualification guard.",
                runner_ups=sorted(qualified, key=lambda e: e.total_score, reverse=True)[
                    :3
                ],
            )

        runner_labels = [_label(item) for item in result.runner_up_labels if item]
        runner_ups = [
            label_map[item]
            for item in runner_labels
            if item in label_map and label_map[item].candidate_id != chosen.candidate_id
        ][:3]
        if not runner_ups:
            runner_ups = [
                e
                for e in sorted(qualified, key=lambda e: e.total_score, reverse=True)
                if e.candidate_id != chosen.candidate_id
            ][:3]

        winner_candidate = candidate_by_id.get(chosen.candidate_id)
        return WinnerSelection(
            has_winner=True,
            winner=chosen,
            winner_solution=(
                winner_candidate.model_dump_json() if winner_candidate else None
            ),
            runner_ups=runner_ups,
            debate_summary=result.rationale,
            selection_methodology=(
                "Independent critic selection over anonymised qualified finalists, "
                "guarded by mandatory gates and a 60/100 minimum. "
                f"Critic confidence: {result.confidence:.2f}."
            ),
        )

    # ------------------------------------------------------------------
    # Evidence assembly
    # ------------------------------------------------------------------

    @staticmethod
    def _evidence_bundle(
        problem: ProblemCandidate | None, gap: InnovationGap | None
    ) -> SearchBundle:
        bundle = SearchBundle(query=problem.title if problem else "candidate")
        seen: set[str] = set()
        if problem:
            for item in problem.evidence:
                if item.source_url and item.source_url not in seen:
                    seen.add(item.source_url)
                    bundle.results.append(
                        SearchResult(
                            title=item.description[:120],
                            url=item.source_url,
                            snippet=item.description,
                            source_type=item.source_type,
                            reliability=item.credibility,
                        )
                    )
        if gap:
            for source in gap.research_sources:
                if source.url and source.url not in seen:
                    seen.add(source.url)
                    bundle.results.append(
                        SearchResult(
                            title=source.title,
                            url=source.url,
                            snippet=source.description or "",
                            source_type=source.source_type.value,
                            reliability=source.reliability,
                        )
                    )
        return bundle


def _label(value: str | None) -> str:
    """Extract a finalist label (A-J) from strings like "Finalist A" or "A"."""
    text = (value or "").strip().upper()
    match = re.search(r"\b([A-J])\b", text)
    if match:
        return match.group(1)
    stripped = text.replace("FINALIST", "").strip(" .:-")
    return stripped[:1] if stripped[:1] in "ABCDEFGHIJ" else ""
