"""Agent 3 — Global Innovation and Existing-Solution Research Agent."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from config.logging_config import get_logger
from src.agents.base import BaseAgent, evidence_lines
from src.models.domain import ProblemCandidate
from src.models.research import (
    ExistingSolution,
    InnovationGap,
    InnovationReport,
    OpportunityClassification,
    PublicationCategory,
    ResearchSource,
    VerificationLevel,
)
from src.research.evidence_aggregator import EvidenceAggregator

logger = get_logger("agents.innovation_research")

SYSTEM = """You are the Global Innovation and Existing-Solution Research Agent.
You investigate what already exists before anyone claims originality.
Rules:
- Only describe solutions that appear in the supplied evidence.
- Never invent a product, startup, repository, paper, URL, star count or feature.
- A single search that finds nothing is NOT proof that a problem is unsolved.
- Distinguish open-source repositories from complete commercial solutions.
- Be willing to classify an opportunity as commonly solved or insufficient evidence.
Return JSON only.
"""


class ExistingSolutionLLM(BaseModel):
    evidence_index: int
    name: str
    solution_type: str = "open_source"
    description: str = ""
    what_it_solves: str = ""
    target_users: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    disadvantages: list[str] = Field(default_factory=list)
    unsolved_aspects: list[str] = Field(default_factory=list)
    missing_features: list[str] = Field(default_factory=list)
    adoption_barriers: list[str] = Field(default_factory=list)


class GapLLM(BaseModel):
    classification: str = "insufficient_evidence"
    gap_description: str = ""
    differentiation_potential: str = ""
    evidence_summary: str = ""
    existing_solutions: list[ExistingSolutionLLM] = Field(default_factory=list)
    confidence: float = Field(default=0.4, ge=0, le=1)

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: Any) -> Any:
        if isinstance(v, (int, float)) and v > 1:
            return min(1.0, v / 100.0)
        return v


class InnovationBatchLLM(BaseModel):
    gaps: list[GapLLM] = Field(default_factory=list)


class InnovationResearchAgent(BaseAgent):
    """Finds real competitors, repositories and papers for each problem."""

    name = "innovation_research"
    description = "Investigates existing solutions and the remaining innovation gap"

    def run(
        self,
        session_id: str,
        problems: list[ProblemCandidate],
        *,
        theme: str = "",
        intelligence_context: str = "",
    ) -> InnovationReport:
        report = InnovationReport()
        for problem in problems:
            bundle = self.research.multi_search(
                session_id,
                [
                    f"{problem.title} {problem.domain}",
                    f"{problem.title} existing solution",
                    f"{problem.domain} {problem.subdomain or ''} open source",
                ],
                source_types=[
                    "github",
                    "openalex",
                    "crossref",
                    "arxiv",
                    "hackernews",
                    "rss",
                ],
                limit=5,
                max_results=18,
            )
            # Ensure problem evidence is enriched with relevant research papers retrieved by Agent 3
            EvidenceAggregator.aggregate_problem_evidence(problem, bundle.results, min_sources=2)
            github_results = [r for r in bundle.results if r.source_type == "github"]

            prompt = f"""Hackathon theme: {theme}
Problem: {problem.title}
Description: {problem.description}
Domain: {problem.domain} / {problem.subdomain or "general"}
Affected people: {problem.affected_people}
Existing-solution hints from discovery: {problem.inadequate_solutions}
Recent intelligence: {intelligence_context[:1500] or "(none)"}

REAL GITHUB REPOSITORIES FOUND ({len(github_results)}) — metadata only, cite via the numbered list below:
{_github_context(github_results)}

COMBINED RETRIEVED EVIDENCE (cite these 1-based indices only):
{evidence_lines(bundle, max_items=18)}

Requirements:
- Classify the opportunity honestly: commonly_solved, partially_solved,
  existing_solution_with_important_limitations, underserved_problem,
  potentially_differentiated_opportunity, or insufficient_evidence.
- Describe what each cited solution actually solves and where it falls short.
- Every existing solution must cite a valid evidence_index (1-based, from the
  combined list). Do not list anything you cannot cite.
- Compare repositories by functionality, activity and documentation when the
  metadata is available.
- If no solution was found, use insufficient_evidence and state that absence of
  evidence is not evidence of absence.
- Explain precisely what gap remains and why it matters."""
            try:
                gap_llm = self.llm.generate_json(prompt, GapLLM, SYSTEM)
            except Exception as exc:  # noqa: BLE001 - continue other problems
                logger.warning("Innovation research failed for %s: %s", problem.id, exc)
                report.gaps.append(
                    InnovationGap(
                        problem_candidate_id=problem.id or "",
                        classification=OpportunityClassification.INSUFFICIENT_EVIDENCE,
                        gap_description=f"Research failed: {exc}",
                        evidence_summary="No reliable conclusion could be drawn.",
                        confidence=0.1,
                    )
                )
                continue

            classification = _classification(gap_llm.classification)
            if not bundle.results:
                classification = OpportunityClassification.INSUFFICIENT_EVIDENCE
                gap_llm.gap_description = (
                    "No existing-solution evidence was retrieved. This is an "
                    "evidence gap, not proof that the problem is unsolved."
                )

            existing: list[ExistingSolution] = []
            used_urls: set[str] = set()
            for item in gap_llm.existing_solutions[:12]:
                if not (1 <= item.evidence_index <= len(bundle.results)):
                    continue
                source = bundle.results[item.evidence_index - 1]
                if source.url in used_urls:
                    continue
                used_urls.add(source.url)
                existing.append(
                    ExistingSolution(
                        name=item.name or source.title,
                        solution_type=item.solution_type,
                        description=item.description or source.snippet[:500],
                        url=source.url,
                        what_it_solves=item.what_it_solves,
                        target_users=item.target_users[:6],
                        technologies=item.technologies[:8],
                        disadvantages=item.disadvantages[:6],
                        unsolved_aspects=item.unsolved_aspects[:6],
                        missing_features=item.missing_features[:6],
                        adoption_barriers=item.adoption_barriers[:6],
                        source=ResearchSource(
                            url=source.url,
                            title=source.title,
                            source_type=_source_type(source.source_type),
                            publication_category=_pub_category(getattr(source, "publication_category", "web_resource")),
                            verification_level=_ver_level(getattr(source, "verification_level", "metadata_validated")),
                            description=source.snippet[:800],
                            metadata=source.metadata,
                            reliability=source.reliability,
                        ),
                    )
                )
                self.repository.save_existing_solution(
                    session_id, problem.id, existing[-1]
                )

            gap = InnovationGap(
                problem_candidate_id=problem.id or "",
                classification=classification,
                existing_solutions=existing,
                github_projects=self.research.github_projects(
                    session_id,
                    f"{problem.title} {problem.domain}",
                    limit=6,
                ),
                gap_description=gap_llm.gap_description,
                differentiation_potential=gap_llm.differentiation_potential,
                evidence_summary=gap_llm.evidence_summary,
                research_sources=[
                    ResearchSource(
                        url=r.url,
                        title=r.title,
                        source_type=_source_type(r.source_type),
                        publication_category=_pub_category(getattr(r, "publication_category", "web_resource")),
                        verification_level=_ver_level(getattr(r, "verification_level", "metadata_validated")),
                        description=r.snippet[:800],
                        metadata=r.metadata,
                        reliability=r.reliability,
                    )
                    for r in bundle.results[:20]
                    if r.url
                ],
                confidence=gap_llm.confidence,
            )
            # Enrich gap summary and differentiation if LLM output was sparse
            EvidenceAggregator.enrich_gap_summary(gap)
            report.gaps.append(gap)
            report.total_solutions_found += len(existing)
            report.total_github_projects += len(gap.github_projects)
            report.research_papers_reviewed += sum(
                1
                for r in bundle.results
                if r.source_type in {"arxiv", "openalex", "crossref"}
            )

        self._save(session_id, "innovation_report", report)
        return report


def _pub_category(value: str) -> PublicationCategory:
    try:
        return PublicationCategory(value)
    except ValueError:
        return PublicationCategory.WEB_RESOURCE


def _ver_level(value: str) -> VerificationLevel:
    try:
        return VerificationLevel(value)
    except ValueError:
        return VerificationLevel.RETRIEVED_RECORD


def _classification(value: str) -> OpportunityClassification:
    normalized = (value or "").strip().lower()
    aliases = {
        "commonly solved": "commonly_solved",
        "partially solved": "partially_solved",
        "limited solution": "existing_solution_with_important_limitations",
        "underserved": "underserved_problem",
        "differentiated": "potentially_differentiated_opportunity",
    }
    normalized = aliases.get(normalized, normalized)
    try:
        return OpportunityClassification(normalized)
    except ValueError:
        return OpportunityClassification.INSUFFICIENT_EVIDENCE


def _source_type(value: str):
    from src.models.research import SourceType

    try:
        return SourceType(value)
    except ValueError:
        return SourceType.WEB


def _github_context(results: list) -> str:
    if not results:
        return "(no repositories found)"
    lines = []
    for index, result in enumerate(results, start=1):
        meta = result.metadata
        lines.append(
            f"[G{index}] {result.title} | stars={meta.get('stars', 0)} | "
            f"forks={meta.get('forks', 0)} | language={meta.get('language')} | "
            f"updated={(meta.get('updated_at') or '')[:10]} | archived={meta.get('archived')}\n"
            f"{result.url}\n{result.snippet[:400]}"
        )
    return "\n\n".join(lines)
