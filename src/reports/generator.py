"""Final report generator — all 24 required sections.

The report is assembled from persisted structured findings. It distinguishes
verified facts, inferred findings and speculative opportunities rather than
presenting model prose as fact.
"""

from __future__ import annotations

from pathlib import Path

from config.logging_config import get_logger
from config.settings import get_settings
from src.database.repository import Repository
from src.models.candidate import CandidateSolution, FeasibilityReport
from src.models.domain import DomainMap
from src.models.evaluation import CandidateEvaluation, FinalEvaluationReport
from src.models.hackathon import HackathonInput, HackathonIntelligence
from src.models.pipeline import PipelineResult
from src.models.report import FinalReport, ReportMetadata, ReportSection
from src.models.research import InnovationReport

logger = get_logger("reports.generator")


def _bullets(items: list[str], empty: str = "_None recorded._") -> str:
    return "\n".join(f"- {item}" for item in items) if items else empty


def _quote(text: str | None, limit: int = 2500) -> str:
    return (text or "").strip()[:limit] or "_Not recorded._"


def _evaluation_table(evaluations: list[CandidateEvaluation]) -> str:
    if not evaluations:
        return "_No candidates were evaluated._"
    lines = [
        "| Rank | Candidate | Domain | Score | Gates | Debate |",
        "|---:|---|---|---:|---|---|",
    ]
    for evaluation in sorted(evaluations, key=lambda e: e.total_score, reverse=True):
        gates = "PASS" if evaluation.all_gates_passed else "FAIL"
        lines.append(
            f"| {evaluation.rank or '-'} | {evaluation.candidate_title[:70]} | "
            f"{evaluation.domain} | {evaluation.total_score:.1f} | {gates} | "
            f"{evaluation.debate_recommendation or '-'} |"
        )
    return "\n".join(lines)


def _score_table(evaluation: CandidateEvaluation | None) -> str:
    if not evaluation:
        return "_No winning score breakdown is available._"
    lines = [
        "| Criterion | Weight | Score /10 | Weighted | Justification |",
        "|---|---:|---:|---:|---|",
    ]
    for score in evaluation.scores:
        lines.append(
            f"| {score.name} | {score.weight} | {score.score:.1f} | "
            f"{score.weighted_score:.1f} | {score.justification[:220]} |"
        )
    lines.append(
        f"| **Total (after debate)** | **100** |  | **{evaluation.total_score:.1f}** | "
        f"base {evaluation.base_score:.1f}, debate {evaluation.debate_adjustment:+.1f} |"
    )
    return "\n".join(lines)


def _gates_table(evaluation: CandidateEvaluation | None) -> str:
    if not evaluation:
        return "_No gate results are available._"
    lines = ["| Mandatory gate | Status | Justification |", "|---|---|---|"]
    for gate in evaluation.quality_gates:
        lines.append(
            f"| {gate.name} | {gate.status.value.upper()} | {gate.justification[:240]} |"
        )
    return "\n".join(lines)


class ReportGenerator:
    """Builds, persists and exports the final report."""

    def __init__(self, repository: Repository | None = None) -> None:
        self.repository = repository or Repository()
        self.settings = get_settings()

    def generate(
        self,
        result: PipelineResult,
        final_evaluation: FinalEvaluationReport,
        *,
        continuous_intelligence_note: str = "",
        model_name: str = "",
        llm_stats: dict | None = None,
    ) -> FinalReport:
        hackathon = result.input
        intelligence = result.intelligence
        domain_map = result.domain_map
        innovation = result.innovation_report
        feasibility = result.feasibility
        winner = final_evaluation.winner
        evaluations = final_evaluation.evaluations

        winner_evaluation = winner.winner if winner.has_winner else None
        winner_solution = self._winner_solution(winner_evaluation, feasibility)
        winner_problem = None
        if domain_map and winner_solution:
            winner_problem = next(
                (
                    p
                    for p in domain_map.problem_candidates
                    if p.id == winner_solution.problem_candidate_id
                ),
                None,
            )

        sections: list[ReportSection] = []
        sections.append(
            ReportSection(
                number=1,
                title="Executive summary",
                content=self._executive_summary(
                    hackathon, intelligence, domain_map, innovation, winner
                ),
            )
        )
        sections.append(
            ReportSection(
                number=2,
                title="Hackathon organizer intelligence",
                content=self._organizer_section(intelligence),
            )
        )
        sections.append(
            ReportSection(
                number=3,
                title="Organizer goals and judging expectations",
                content=self._goals_section(intelligence),
            )
        )
        sections.append(
            ReportSection(
                number=4,
                title="Discovered domains and relevance",
                content=self._domains_section(domain_map),
            )
        )
        sections.append(
            ReportSection(
                number=5,
                title="Research findings for relevant domains",
                content=self._domain_findings(domain_map),
            )
        )
        sections.append(
            ReportSection(
                number=6,
                title="Problem candidates discovered",
                content=self._problems_section(domain_map),
            )
        )
        sections.append(
            ReportSection(
                number=7,
                title="Existing products and GitHub projects",
                content=self._existing_solutions_section(innovation),
            )
        )
        sections.append(
            ReportSection(
                number=8,
                title="Innovation gaps",
                content=self._gaps_section(innovation),
            )
        )
        sections.append(
            ReportSection(
                number=9,
                title="Candidate comparison",
                content=_evaluation_table(evaluations),
            )
        )
        sections.append(
            ReportSection(
                number=10,
                title="Adversarial debate summary",
                content=self._debate_section(final_evaluation),
            )
        )
        sections.append(
            ReportSection(
                number=11,
                title="Final winning problem statement",
                content=self._winner_section(winner, winner_solution, winner_problem),
            )
        )
        sections.append(
            ReportSection(
                number=12,
                title="Target users",
                content=_bullets(
                    winner_solution.target_users if winner_solution else []
                ),
            )
        )
        sections.append(
            ReportSection(
                number=13,
                title="Real-world importance and evidence",
                content=self._importance_section(winner_solution, winner_problem),
                evidence_links=[
                    e.source_url
                    for e in (winner_problem.evidence if winner_problem else [])
                    if e.source_url
                ],
            )
        )
        sections.append(
            ReportSection(
                number=14,
                title="Proposed solution",
                content=self._solution_section(winner_solution),
            )
        )
        sections.append(
            ReportSection(
                number=15,
                title="Unique differentiation",
                content=_quote(
                    winner_solution.unique_differentiation if winner_solution else ""
                ),
            )
        )
        sections.append(
            ReportSection(
                number=16,
                title="Technical feasibility",
                content=self._feasibility_section(winner_solution),
            )
        )
        sections.append(
            ReportSection(
                number=17,
                title="Development requirements",
                content=self._requirements_section(winner_solution),
            )
        )
        sections.append(
            ReportSection(
                number=18,
                title="Advantages and disadvantages",
                content=self._advantages_section(winner_solution),
            )
        )
        sections.append(
            ReportSection(
                number=19,
                title="Risk mitigation",
                content=self._risk_section(winner_solution),
            )
        )
        sections.append(
            ReportSection(
                number=20,
                title="Organizer and theme alignment",
                content=self._alignment_section(
                    hackathon, intelligence, winner_solution, winner_evaluation
                ),
            )
        )
        sections.append(
            ReportSection(
                number=21,
                title="Final scoring breakdown",
                content=_score_table(winner_evaluation)
                + "\n\n### Mandatory quality gates\n\n"
                + _gates_table(winner_evaluation),
            )
        )
        sections.append(
            ReportSection(
                number=22,
                title="Evidence links",
                content=self._evidence_section(
                    intelligence, domain_map, innovation, feasibility
                ),
            )
        )
        sections.append(
            ReportSection(
                number=23,
                title="Unresolved questions and limitations",
                content=self._limitations_section(
                    intelligence, innovation, winner, llm_stats or {}
                ),
            )
        )
        sections.append(
            ReportSection(
                number=24,
                title="Short runner-up comparison",
                content=self._runner_up_section(winner, evaluations),
            )
        )

        evidence_links = self._collect_evidence(
            intelligence, domain_map, innovation, feasibility
        )
        metadata = ReportMetadata(
            report_id=f"R-{result.session_id[:8]}",
            session_id=result.session_id,
            hackathon_theme=hackathon.theme,
            hackathon_name=hackathon.name,
            generation_time_seconds=round(result.duration_seconds, 2),
            total_domains_explored=domain_map.total_domains_explored
            if domain_map
            else 0,
            total_problems_found=domain_map.total_problems_found if domain_map else 0,
            total_solutions_analyzed=(
                innovation.total_solutions_found + innovation.total_github_projects
                if innovation
                else 0
            ),
            total_candidates_evaluated=len(evaluations),
            model_used=model_name,
        )
        sources = self.repository.get_research_sources(result.session_id)
        retrieval_dates = sorted(
            {row["retrieved_at"] for row in sources if row.get("retrieved_at")}
        )
        data_freshness = {
            "research_sources_tracked": str(len(sources)),
            "oldest_retrieval": retrieval_dates[0] if retrieval_dates else "unknown",
            "newest_retrieval": retrieval_dates[-1] if retrieval_dates else "unknown",
            "continuous_intelligence": continuous_intelligence_note
            or "Not included in this run.",
            "model": model_name or "unknown",
        }
        report = FinalReport(
            metadata=metadata,
            sections=sections,
            evidence_links=evidence_links,
            unresolved_questions=self._unresolved_questions(intelligence, winner),
            data_freshness=data_freshness,
            limitations=[
                (
                    "Research is limited to free public sources reachable at run time; "
                    "paywalled databases and private company data are not accessed."
                ),
                (
                    "Search APIs may rate-limit or omit results; absence of evidence is "
                    "not proof that a solution does not exist."
                ),
                (
                    "Scores are structured judgements from one local model, not ground "
                    "truth. They are constrained by evidence gates and adversarial review."
                ),
                (
                    "Organiser intentions are partly inferred from public material unless "
                    "official rules were supplied."
                ),
                (
                    "Hackathon outcomes also depend on execution, presentation and judging "
                    "subjectivity; this report does not guarantee a win."
                ),
            ],
        )
        self._persist(report)
        return report

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    @staticmethod
    def _executive_summary(
        hackathon: HackathonInput,
        intelligence: HackathonIntelligence | None,
        domain_map: DomainMap | None,
        innovation: InnovationReport | None,
        winner,
    ) -> str:
        if winner.has_winner and winner.winner:
            outcome = (
                f"**Winning candidate:** {winner.winner.candidate_title} "
                f"({winner.winner.domain}), scoring **{winner.winner.total_score:.1f}/100** "
                "after adversarial debate and passing all mandatory quality gates."
            )
        else:
            outcome = (
                "**No candidate qualified as a winner.** HackathonIQ rejected every "
                f"candidate rather than manufacture a weak recommendation. "
                f"Reason: {winner.rejection_reason or 'quality gates not met.'}"
            )
        return (
            f"**Hackathon theme:** {hackathon.theme}\n\n"
            f"**Hackathon:** {hackathon.name or 'not supplied'}\n\n"
            f"{outcome}\n\n"
            f"The run explored **{domain_map.total_domains_explored if domain_map else 0} "
            f"dynamically discovered domains** and **"
            f"{domain_map.total_problems_found if domain_map else 0} evidence-backed "
            f"problem candidates**, then investigated **"
            f"{(innovation.total_solutions_found + innovation.total_github_projects) if innovation else 0} "
            "existing solutions and repositories** before cross-domain comparison.\n\n"
            f"**Organiser signal:** "
            f"{'; '.join(intelligence.organizer_goals[:3] if intelligence else []) or 'Insufficient verified organiser intelligence.'}\n\n"
            "This report distinguishes verified facts, inferred findings and "
            "speculative opportunities. All external claims retain source links."
        )

    @staticmethod
    def _organizer_section(intelligence: HackathonIntelligence | None) -> str:
        if not intelligence:
            return "_No organiser intelligence was produced._"
        organizer = intelligence.organizer
        verified = _bullets(
            intelligence.verified_facts, "_No verified facts recorded._"
        )
        assumptions = _bullets(intelligence.assumptions, "_No assumptions recorded._")

        constraints_by_cat: dict[str, list[str]] = {}
        for cc in getattr(intelligence, "categorized_constraints", []):
            cat_label = cc.category.value.replace("_", " ").title()
            constraints_by_cat.setdefault(cat_label, []).append(
                f"{cc.description} {'[MANDATORY]' if cc.is_mandatory else '[OPTIONAL/HYPOTHESIS]'}"
            )

        constraint_blocks = []
        for cat_label, items in constraints_by_cat.items():
            constraint_blocks.append(f"**{cat_label}:**\n{_bullets(items)}")
        provenance_str = "\n\n".join(constraint_blocks) if constraint_blocks else "_No categorized constraints recorded._"

        org_name = organizer.name if organizer else "None specified (General Theme Research Mode)"
        return (
            f"**Organiser:** {org_name}\n\n"
            f"**Mission (reported/inferred):** {_quote(organizer.mission if organizer else '', 800)}\n\n"
            f"**Ideology:** {_quote(organizer.ideology if organizer else '', 600)}\n\n"
            f"**Objectives:**\n{_bullets(organizer.objectives if organizer else [])}\n\n"
            f"**Constraint Provenance:**\n{provenance_str}\n\n"
            f"**Verified facts:**\n{verified}\n\n"
            f"**Assumptions / unverified inferences:**\n{assumptions}\n\n"
            f"**Judges found:** {len(intelligence.judges)} | "
            f"**Sponsors found:** {len(intelligence.sponsors)} | "
            f"**Previous projects found:** {len(intelligence.previous_projects)}\n\n"
            f"**Judging criteria:**\n"
            f"{_bullets([c.criterion + (f' (weight {c.weight})' if c.weight else '') for c in intelligence.judging_criteria])}\n\n"
            f"**Submission requirements:**\n{_bullets(intelligence.submission_requirements)}\n\n"
            f"**Technical restrictions:**\n{_bullets(intelligence.technical_restrictions)}\n\n"
            f"**Source URLs:**\n{_bullets(intelligence.research_sources)}"
        )

    @staticmethod
    def _goals_section(intelligence: HackathonIntelligence | None) -> str:
        if not intelligence:
            return "_No organiser goals were inferred._"
        return (
            f"**Goals:**\n{_bullets(intelligence.organizer_goals)}\n\n"
            f"**Recurring priorities across editions (where evidenced):**\n"
            f"{_bullets(intelligence.recurring_priorities)}\n\n"
            f"**Expected outcomes:**\n{_bullets(intelligence.expected_outcomes)}\n\n"
            f"**Target participants:** {_quote(intelligence.target_participants, 500)}\n\n"
            f"**Time limit:** "
            f"{intelligence.time_limit_hours if intelligence.time_limit_hours else 'not verified'} hours"
        )

    @staticmethod
    def _domains_section(domain_map: DomainMap | None) -> str:
        if not domain_map or not domain_map.domains:
            return "_No domains were discovered._"
        blocks = []
        if domain_map.stopping_reason:
            blocks.append(f"> **Dynamic Domain Exploration Status:** {domain_map.stopping_reason}")

        for domain in domain_map.domains:
            blocks.append(
                f"### {domain.name} ({domain.relevance_type.value})\n"
                f"{domain.relevance_explanation}\n\n"
                f"**Subdomains:** {', '.join(domain.subdomains) or 'none listed'}\n\n"
                f"**Interdisciplinary links:** {', '.join(domain.interdisciplinary_links) or 'none listed'}\n\n"
                f"**Theme connections:** {'; '.join(domain.connections_to_theme) or 'none listed'}\n\n"
                f"**Confidence:** {domain.confidence:.2f}"
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _domain_findings(domain_map: DomainMap | None) -> str:
        if not domain_map:
            return "_No domain research findings._"
        lines = []
        for domain in domain_map.domains:
            problems = [
                p for p in domain_map.problem_candidates if p.domain == domain.name
            ]
            lines.append(
                f"### {domain.name}\n"
                f"{len(problems)} problem candidate(s); "
                f"{len(domain.evidence)} source link(s) recorded.\n\n"
                + _bullets(
                    [
                        f"{p.title} — {len(p.evidence)} evidence item(s), "
                        f"seriousness={p.seriousness}, confidence={p.confidence:.2f}"
                        for p in problems
                    ]
                )
            )
        return "\n\n".join(lines)

    @staticmethod
    def _problems_section(domain_map: DomainMap | None) -> str:
        if not domain_map or not domain_map.problem_candidates:
            return "_No problem candidates were discovered._"
        lines = []
        for problem in domain_map.problem_candidates:
            evidence = (
                "\n".join(
                    f"  - [{e.source_type}] {e.source_url or 'no URL'} — {e.description[:240]}"
                    for e in problem.evidence[:6]
                )
                or "  - No evidence retrieved (gate will fail)."
            )
            lines.append(
                f"### {problem.id}: {problem.title}\n"
                f"**Domain:** {problem.domain} / {problem.subdomain or 'general'}\n\n"
                f"{problem.description}\n\n"
                f"**Affected:** {', '.join(problem.affected_people) or 'not specified'}\n\n"
                f"**Seriousness:** {problem.seriousness} | "
                f"**Confidence:** {problem.confidence:.2f} | "
                f"**Generic:** {'yes' if problem.is_generic else 'no'}\n\n"
                f"**Evidence:**\n{evidence}\n\n"
                f"**Why existing solutions are inadequate:** "
                f"{'; '.join(problem.inadequate_solutions) or 'not established'}\n\n"
                f"**Overlooked needs:** {'; '.join(problem.overlooked_needs) or 'none recorded'}\n\n"
                f"**Future opportunity:** {'; '.join(problem.future_potential) or 'none recorded'}"
            )
        return "\n\n---\n\n".join(lines)

    @staticmethod
    def _existing_solutions_section(innovation: InnovationReport | None) -> str:
        if not innovation or not innovation.gaps:
            return "_No existing-solution research was completed._"
        lines = []
        for gap in innovation.gaps:
            solutions = (
                "\n".join(
                    f"- **{s.name}** ({s.solution_type}) — {s.url or 'no URL'}\n"
                    f"  Solves: {s.what_it_solves or s.description[:300]}\n"
                    f"  Limitations: {'; '.join(s.disadvantages) or 'not documented'}"
                    for s in gap.existing_solutions
                )
                or "- No verified existing solution identified."
            )
            projects = (
                "\n".join(
                    f"- **{p.name}** — {p.stars} stars, {p.forks} forks, "
                    f"{p.language or 'unknown language'}, active={p.is_active}, {p.url}"
                    for p in gap.github_projects
                )
                or "- No GitHub project identified."
            )
            lines.append(
                f"### Problem {gap.problem_candidate_id}\n"
                f"**Classification:** {gap.classification.value}\n\n"
                f"**Existing solutions:**\n{solutions}\n\n"
                f"**GitHub projects:**\n{projects}"
            )
        return "\n\n".join(lines)

    @staticmethod
    def _gaps_section(innovation: InnovationReport | None) -> str:
        if not innovation:
            return "_No innovation-gap analysis._"
        return "\n\n".join(
            f"### Problem {gap.problem_candidate_id}\n"
            f"**Classification:** {gap.classification.value}\n\n"
            f"**Gap:** {gap.gap_description or 'not described'}\n\n"
            f"**Differentiation potential:** {gap.differentiation_potential or 'not established'}\n\n"
            f"**Evidence summary:** {gap.evidence_summary or 'none'}\n\n"
            f"**Confidence:** {gap.confidence:.2f}"
            for gap in innovation.gaps
        )

    @staticmethod
    def _debate_section(final_evaluation: FinalEvaluationReport) -> str:
        if not final_evaluation.debates:
            return "_No debate rounds were run._"
        lines = []
        for debate in final_evaluation.debates:
            lines.append(
                f"### Candidate {debate.candidate_id}\n"
                f"Score before: {debate.score_before_debate:.1f} | "
                f"after: {debate.score_after_debate:.1f} | "
                f"recommendation: **{debate.recommendation}**\n\n"
                f"{debate.final_assessment or ''}\n"
            )
            for round_ in debate.rounds:
                lines.append(
                    f"**Round {round_.round_number}** — resolved={round_.criticism_resolved}, "
                    f"adjustment={round_.score_adjustment:+.1f}\n\n"
                    f"Criticism: {round_.criticism}\n\n"
                    f"Rebuttal: {round_.rebuttal}\n"
                )
        return "\n\n".join(lines)

    @staticmethod
    def _winner_section(winner, solution: CandidateSolution | None, problem) -> str:
        if not winner.has_winner or not solution:
            return (
                "**No winner was selected.**\n\n"
                f"{winner.rejection_reason or 'No candidate met the mandatory quality gates.'}\n\n"
                "This is an honest negative result, not a failure to generate ideas. "
                "Strengthen the evidence base or refine the theme and run again."
            )
        return (
            f"# {solution.title}\n\n"
            f"**Problem statement:** {problem.description if problem else solution.problem_statement}\n\n"
            f"**Problem candidate:** {solution.problem_candidate_id} | "
            f"**Domain:** {solution.domain}\n\n"
            f"**Selected by:** independent adversarial critic over anonymised finalists.\n\n"
            f"**Selection rationale:** {winner.debate_summary or 'See final evaluation.'}"
        )

    @staticmethod
    def _importance_section(solution, problem) -> str:
        if not solution:
            return "_No winner to assess._"
        evidence = (
            "\n".join(
                f"- {e.description[:400]} — {e.source_url or 'no URL'} "
                f"(credibility {e.credibility:.2f})"
                for e in (problem.evidence if problem else [])
            )
            or "_No problem evidence recorded._"
        )
        return (
            f"**User pain point:** {_quote(solution.user_pain_point)}\n\n"
            f"**Affected people/organisations:** "
            f"{', '.join(problem.affected_people) if problem else 'not specified'}\n\n"
            f"**Seriousness:** {problem.seriousness if problem else 'unknown'}\n\n"
            f"**Evidence:**\n{evidence}\n\n"
            f"**Supporting evidence summary:**\n{_bullets(solution.supporting_evidence)}"
        )

    @staticmethod
    def _solution_section(solution: CandidateSolution | None) -> str:
        if not solution:
            return "_No winning solution._"
        return (
            f"{_quote(solution.proposed_solution, 6000)}\n\n"
            f"**Conceptual architecture:**\n\n{_quote(solution.technical_architecture, 5000)}\n\n"
            f"**Hackathon demo plan:**\n\n{_quote(solution.hackathon_demo_plan, 2500)}"
        )

    @staticmethod
    def _feasibility_section(solution: CandidateSolution | None) -> str:
        if not solution:
            return "_No winner to assess._"
        return (
            f"**Development complexity:** {solution.development_complexity}\n\n"
            f"**Estimated build time:** {solution.estimated_hours:.1f} hours\n\n"
            f"**Feasibility score:** {solution.feasibility_score:.2f} / 1.00\n\n"
            f"**Estimated cost:** {solution.estimated_cost}\n\n"
            f"**Infrastructure:** {', '.join(solution.infrastructure_requirements) or 'not specified'}\n\n"
            f"**Dependencies:** {', '.join(solution.dependencies) or 'not specified'}"
        )

    @staticmethod
    def _requirements_section(solution: CandidateSolution | None) -> str:
        if not solution:
            return "_No winner to assess._"
        data = (
            "\n".join(
                f"- [{r.category}] {r.description} — availability={r.availability}, "
                f"cost={r.cost}, risk={r.risk_level}"
                for r in solution.data_requirements
            )
            or "- None recorded."
        )
        api = (
            "\n".join(
                f"- [{r.category}] {r.description} — availability={r.availability}, "
                f"cost={r.cost}, risk={r.risk_level}"
                for r in solution.api_requirements
            )
            or "- None recorded."
        )
        tech = ", ".join(solution.relevant_technologies) or "not specified"
        return (
            f"**Technologies:** {tech}\n\n"
            f"**Data requirements:**\n{data}\n\n"
            f"**API requirements:**\n{api}"
        )

    @staticmethod
    def _advantages_section(solution: CandidateSolution | None) -> str:
        if not solution:
            return "_No winner to assess._"
        return (
            f"**Advantages:**\n{_bullets(solution.advantages)}\n\n"
            f"**Disadvantages:**\n{_bullets(solution.disadvantages)}"
        )

    @staticmethod
    def _risk_section(solution: CandidateSolution | None) -> str:
        if not solution:
            return "_No winner to assess._"
        risks = (
            "\n".join(
                f"- **[{r.severity}/{r.likelihood}] {r.risk_type}:** {r.description} "
                f"— mitigation: {r.mitigation or 'none stated'}"
                for r in solution.risks
            )
            or "- No risks recorded (this itself is a warning sign)."
        )
        return f"{risks}\n\n**Mitigation strategies:**\n{_bullets(solution.mitigation_strategies)}"

    @staticmethod
    def _alignment_section(
        hackathon: HackathonInput,
        intelligence: HackathonIntelligence | None,
        solution: CandidateSolution | None,
        evaluation: CandidateEvaluation | None,
    ) -> str:
        if not solution:
            return "_No winner to assess._"
        relevance = next(
            (
                s
                for s in (evaluation.scores if evaluation else [])
                if s.name == "Hackathon theme relevance"
            ),
            None,
        )
        alignment = next(
            (
                s
                for s in (evaluation.scores if evaluation else [])
                if s.name == "Organizer and sponsor alignment"
            ),
            None,
        )
        return (
            f"**Theme:** {hackathon.theme}\n\n"
            f"**Problem-to-theme connection:** {_quote(solution.identified_gap, 1200)}\n\n"
            f"**Theme relevance score:** "
            f"{f'{relevance.score:.1f}/10 — {relevance.justification}' if relevance else 'not scored'}\n\n"
            f"**Organiser alignment score:** "
            f"{f'{alignment.score:.1f}/10 — {alignment.justification}' if alignment else 'not scored'}\n\n"
            f"**Organiser goals considered:**\n"
            f"{_bullets(intelligence.organizer_goals[:8] if intelligence else [])}"
        )

    def _evidence_section(
        self,
        intelligence: HackathonIntelligence | None,
        domain_map: DomainMap | None,
        innovation: InnovationReport | None,
        feasibility: FeasibilityReport | None,
    ) -> str:
        links = self._collect_evidence(
            intelligence, domain_map, innovation, feasibility
        )
        return _bullets(links, "_No evidence links recorded._")

    @staticmethod
    def _limitations_section(
        intelligence: HackathonIntelligence | None,
        innovation: InnovationReport | None,
        winner,
        llm_stats: dict,
    ) -> str:
        assumptions = _bullets(intelligence.assumptions if intelligence else [])
        insufficient = [
            gap.problem_candidate_id
            for gap in (innovation.gaps if innovation else [])
            if gap.classification.value == "insufficient_evidence"
        ]
        return (
            f"**Unresolved organiser assumptions:**\n{assumptions}\n\n"
            f"**Problems with insufficient existing-solution evidence:** "
            f"{', '.join(insufficient) or 'none'}\n\n"
            f"**Model usage:** {llm_stats.get('calls', 'unknown')} calls, "
            f"{llm_stats.get('failures', 0)} failure(s), "
            f"{llm_stats.get('total_seconds', 0)} seconds of inference.\n\n"
            f"**Selection status:** "
            f"{'winner declared' if winner.has_winner else 'no winner'}; "
            f"{winner.total_candidates_rejected} candidate(s) rejected."
        )

    @staticmethod
    def _runner_up_section(winner, evaluations: list[CandidateEvaluation]) -> str:
        if not winner.runner_ups:
            return "_No qualified runner-up._"
        lines = []
        for evaluation in winner.runner_ups:
            lines.append(
                f"- **{evaluation.candidate_title}** ({evaluation.domain}) — "
                f"{evaluation.total_score:.1f}/100. "
                f"Strengths: {'; '.join(evaluation.strengths[:2]) or 'n/a'}. "
                f"Weaknesses: {'; '.join(evaluation.weaknesses[:2]) or 'n/a'}."
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _winner_solution(
        evaluation: CandidateEvaluation | None,
        feasibility: FeasibilityReport | None,
    ) -> CandidateSolution | None:
        if not evaluation or not feasibility:
            return None
        for candidate in feasibility.candidates:
            if candidate.id == evaluation.candidate_id:
                return candidate
        return None

    @staticmethod
    def _collect_evidence(
        intelligence: HackathonIntelligence | None,
        domain_map: DomainMap | None,
        innovation: InnovationReport | None,
        feasibility: FeasibilityReport | None,
    ) -> list[str]:
        links: list[str] = []
        if intelligence:
            links.extend(intelligence.research_sources)
        if domain_map:
            for problem in domain_map.problem_candidates:
                links.extend(e.source_url for e in problem.evidence if e.source_url)
        if innovation:
            for gap in innovation.gaps:
                links.extend(s.url for s in gap.existing_solutions if s.url)
                links.extend(p.url for p in gap.github_projects if p.url)
                links.extend(s.url for s in gap.research_sources if s.url)
        if feasibility:
            for candidate in feasibility.candidates + feasibility.rejected_candidates:
                links.extend(
                    e for e in candidate.supporting_evidence if e.startswith("http")
                )
        # de-duplicate, preserve order
        return list(dict.fromkeys(link for link in links if link))

    @staticmethod
    def _unresolved_questions(
        intelligence: HackathonIntelligence | None, winner
    ) -> list[str]:
        questions: list[str] = []
        if intelligence:
            questions.extend(intelligence.assumptions[:8])
            if not intelligence.judging_criteria:
                questions.append(
                    "No official judging criteria were verified; scoring alignment is inferred."
                )
        if not winner.has_winner:
            questions.append(
                "Which additional evidence would allow a candidate to pass every gate?"
            )
        questions.append(
            "Will the judges value the chosen problem significance over demo polish?"
        )
        return list(dict.fromkeys(questions))[:12]

    def _persist(self, report: FinalReport) -> None:
        markdown = report.to_markdown()
        reports_dir = Path(self.settings.storage.reports_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / f"{report.metadata.report_id}.md"
        path.write_text(markdown, encoding="utf-8")
        self.repository.save_report(
            session_id=report.metadata.session_id,
            report_json=report.model_dump_json(),
            report_markdown=markdown,
            has_winner=bool(
                any(
                    section.number == 11 and "No winner" not in section.content
                    for section in report.sections
                )
            ),
            winner_title=next(
                (
                    section.content.splitlines()[0].lstrip("# ").strip()
                    for section in report.sections
                    if section.number == 11
                ),
                None,
            ),
        )
        logger.info("Report written to %s", path)
