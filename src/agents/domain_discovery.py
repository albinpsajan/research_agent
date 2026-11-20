"""Agent 2 — Dynamic Domain Discovery and Problem Discovery Agent.

No industry list is hardcoded.  Domains, subdomains and interdisciplinary
links are generated from the theme and then grounded in real retrieved
research.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from config.logging_config import get_logger
from src.agents.base import (
    AgentError,
    BaseAgent,
    evidence_from_indices,
    evidence_lines,
    similarity,
)
from src.models.domain import (
    DiscoveredDomain,
    DomainMap,
    DomainRelevance,
    ProblemCandidate,
)
from src.models.hackathon import HackathonIntelligence
from src.research.evidence_aggregator import EvidenceAggregator

logger = get_logger("agents.domain_discovery")

SYSTEM = """You are the Dynamic Domain Discovery Agent for HackathonIQ.
You discover relevant fields from first principles; you never use a fixed
industry checklist and you never pad the list with generic domains.
Every domain must have a defensible connection to the specific theme and
organiser goals. Every problem must be concrete, attributable to affected
people/organisations, and grounded in supplied evidence. Never invent URLs,
statistics, papers or repositories. Return JSON only.
"""


class DomainLLM(BaseModel):
    name: str
    description: str = ""
    relevance_type: str = "primary"
    relevance_explanation: str = ""
    subdomains: list[str] = Field(default_factory=list)
    connections_to_theme: list[str] = Field(default_factory=list)
    interdisciplinary_links: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list, max_length=5)
    confidence: float = Field(default=0.7, ge=0, le=1)
    relevance_score: float = Field(default=0.75, ge=0, le=1)

    @field_validator("confidence", "relevance_score", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: Any) -> Any:
        if isinstance(v, (int, float)) and v > 1:
            return min(1.0, v / 100.0)
        return v


class DomainListLLM(BaseModel):
    reasoning: str = ""
    domains: list[DomainLLM] = Field(default_factory=list)


class ProblemLLM(BaseModel):
    title: str
    description: str
    subdomain: str = ""
    affected_people: list[str] = Field(default_factory=list)
    seriousness: str = "moderate"
    evidence_indices: list[int] = Field(default_factory=list, max_length=6)
    inadequate_solutions: list[str] = Field(default_factory=list)
    overlooked_needs: list[str] = Field(default_factory=list)
    emerging_opportunities: list[str] = Field(default_factory=list)
    future_potential: list[str] = Field(default_factory=list)
    theme_connection: str = ""
    is_generic: bool = False
    generic_reason: str = ""
    confidence: float = Field(default=0.4, ge=0, le=1)

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: Any) -> Any:
        if isinstance(v, (int, float)) and v > 1:
            return min(1.0, v / 100.0)
        return v


class ProblemListLLM(BaseModel):
    domain_reasoning: str = ""
    problems: list[ProblemLLM] = Field(default_factory=list)


def _relevance(value: str) -> DomainRelevance:
    try:
        return DomainRelevance(value.strip().lower())
    except (ValueError, AttributeError):
        return DomainRelevance.PRIMARY


class DomainDiscoveryAgent(BaseAgent):
    """Discovers domains dynamically, then grounds problems in evidence."""

    name = "domain_discovery"
    description = "Discovers relevant fields and evidence-backed real-world problems"

    def run(
        self,
        session_id: str,
        theme: str,
        intelligence: HackathonIntelligence,
        *,
        intelligence_context: str = "",
        max_domains: int | None = None,
        domain_exploration_budget: int | None = None,
        min_domain_relevance: float | None = None,
        problems_per_domain: int | None = None,
    ) -> DomainMap:
        budget = max_domains or domain_exploration_budget or self.settings.max_domains or 15
        min_relevance = min_domain_relevance or 0.45
        per_domain = problems_per_domain or self.settings.problems_per_domain

        domain_prompt = f"""Hackathon theme: {theme}
Organiser: {intelligence.organizer.name if intelligence.organizer else "None specified (general theme exploration)"}
Organiser goals: {intelligence.organizer_goals[:6]}
Organiser priorities: {intelligence.recurring_priorities[:6]}
Judging criteria: {[c.criterion for c in intelligence.judging_criteria][:8]}
Technical restrictions: {intelligence.technical_restrictions[:6]}
Recent intelligence signals: {intelligence_context[:2000] or "(none)"}

Discover every meaningfully relevant field, subdomain, and interdisciplinary intersection for this specific theme.
Do NOT artificially limit the domain count; explore the full thematic opportunity landscape from first principles.
Think across primary disciplines, operational contexts, and non-obvious intersections.
Do NOT use a fixed industry list. For each domain:
- explain precisely why it matters for THIS theme;
- rate relevance_score (0.0 to 1.0) based on genuine thematic connection and research value;
- list concrete subdomains;
- list interdisciplinary links to other fields;
- propose 2-4 real search queries that would surface credible evidence about
  problems in this domain (include the theme where useful).
Return all genuinely relevant domains, ordered from highest to lowest relevance. Quality over quantity; do not add filler domains."""
        domain_list = self.llm.generate_json(domain_prompt, DomainListLLM, SYSTEM)

        domains: list[DiscoveredDomain] = []
        seen_names: set[str] = set()
        diminishing_returns = False
        stopping_reason = ""

        for item in domain_list.domains:
            key = item.name.strip().lower()
            if not key or key in seen_names:
                continue
            if any(similarity(item.name, existing) > 0.80 for existing in seen_names):
                continue
            rel_score = getattr(item, "relevance_score", 0.75)
            if rel_score < min_relevance:
                logger.info(
                    "Skipping low-relevance domain candidate %s (score %.2f < %.2f)",
                    item.name,
                    rel_score,
                    min_relevance,
                )
                continue

            seen_names.add(key)
            domains.append(
                DiscoveredDomain(
                    name=item.name.strip()[:120],
                    description=item.description,
                    relevance_type=_relevance(item.relevance_type),
                    relevance_explanation=item.relevance_explanation,
                    subdomains=item.subdomains[:10],
                    connections_to_theme=item.connections_to_theme[:8],
                    interdisciplinary_links=item.interdisciplinary_links[:8],
                    confidence=item.confidence,
                    relevance_score=rel_score,
                    is_interdisciplinary_expansion=False,
                    evidence=[],
                )
            )
            if len(domains) >= budget:
                stopping_reason = (
                    f"Domain exploration stopped: Reached exploration budget limit ({budget} domains)."
                )
                break

        if not stopping_reason:
            diminishing_returns = True
            stopping_reason = (
                f"Dynamic exploration completed with {len(domains)} distinct domains. "
                f"Stopping criteria: all meaningful thematic dimensions captured (relevance >= {min_relevance:.2f}); "
                "further expansion produced diminishing returns or redundant overlaps."
            )

        if not domains:
            raise AgentError(
                "The model did not discover any domains. The theme may be too "
                "vague; refine it and retry."
            )

        problems: list[ProblemCandidate] = []
        for domain in domains:
            # Use the LLM's search plan from the matched raw item.
            raw = next(
                (d for d in domain_list.domains if d.name.strip() == domain.name),
                None,
            )
            queries = [
                q.strip() for q in (raw.search_queries if raw else []) if q.strip()
            ]
            if not queries:
                queries = [f"{theme} {domain.name} problems"]
            queries = queries[:4]
            bundle = self.research.multi_search(
                session_id,
                queries,
                source_types=[
                    "openalex",
                    "crossref",
                    "arxiv",
                    "github",
                    "rss",
                    "hackernews",
                ],
                limit=4,
                max_results=14,
            )
            domain.evidence = [r.url for r in bundle.results[:8] if r.url]

            problem_prompt = f"""Hackathon theme: {theme}
Domain: {domain.name}
Why it matters: {domain.relevance_explanation}
Subdomains: {domain.subdomains}
Interdisciplinary links: {domain.interdisciplinary_links}
Organiser goals: {intelligence.organizer_goals[:6]}
Technical restrictions: {intelligence.technical_restrictions[:6]}

RETRIEVED EVIDENCE (cite these 1-based indices only):
{evidence_lines(bundle, max_items=14)}

RECENT INTELLIGENCE (optional context, no URL citations needed):
{intelligence_context[:2000] or "(none)"}

Identify 1-{per_domain} concrete real-world problems in
this domain that are genuinely relevant to the theme. For each problem:
- name who is affected (specific people/organisations, not "everyone");
- state seriousness honestly (low/moderate/high/critical);
- cite 2-3 supplied evidence indices (or at least 1) that provide credible empirical support;
- explain why current solutions are inadequate and what remains overlooked;
- identify an emerging or future-oriented opportunity with a credible basis;
- explain the exact connection to the theme;
- mark is_generic=true if an ordinary chatbot would likely suggest it or if the
  evidence does not support it. Do not inflate confidence.
Avoid generic problems included only to increase candidate count."""
            try:
                problem_list = self.llm.generate_json(
                    problem_prompt, ProblemListLLM, SYSTEM
                )
            except Exception as exc:  # noqa: BLE001 - one domain must not kill the run
                logger.warning("Problem discovery failed for %s: %s", domain.name, exc)
                continue

            for item in problem_list.problems[:per_domain]:
                if not item.title.strip():
                    continue
                evidence = evidence_from_indices(bundle, item.evidence_indices)
                candidate = ProblemCandidate(
                    title=item.title.strip()[:220],
                    description=item.description,
                    domain=domain.name,
                    subdomain=item.subdomain or None,
                    affected_people=item.affected_people[:8],
                    seriousness=(
                        item.seriousness
                        if item.seriousness in {"low", "moderate", "high", "critical"}
                        else "moderate"
                    ),
                    evidence=evidence,
                    inadequate_solutions=item.inadequate_solutions[:8],
                    overlooked_needs=item.overlooked_needs[:8],
                    emerging_opportunities=item.emerging_opportunities[:6],
                    future_potential=item.future_potential[:6],
                    theme_connection=item.theme_connection,
                    is_generic=item.is_generic,
                    confidence=item.confidence,
                )
                # Ensure independent supporting sources from the domain bundle are associated
                EvidenceAggregator.aggregate_problem_evidence(candidate, bundle.results, min_sources=2)
                if self._is_duplicate(candidate, problems):
                    continue
                problems.append(candidate)
                if len(problems) >= self.settings.max_total_problems:
                    break
            if len(problems) >= self.settings.max_total_problems:
                break

        # Cross-domain duplicate detection is repeated after all domains.
        unique: list[ProblemCandidate] = []
        for candidate in sorted(
            problems, key=lambda p: (p.confidence, len(p.evidence)), reverse=True
        ):
            if not self._is_duplicate(candidate, unique):
                unique.append(candidate)
        problems = unique[: self.settings.max_total_problems]

        for index, candidate in enumerate(problems, start=1):
            candidate.id = f"P{index:02d}"

        domain_map = DomainMap(
            theme=theme,
            domains=domains,
            problem_candidates=problems,
            total_domains_explored=len(domains),
            total_problems_found=len(problems),
            exploration_budget=budget,
            exploration_budget_consumed=len(domains),
            stopping_reason=stopping_reason,
            diminishing_returns_reached=diminishing_returns,
        )
        self._save(session_id, "domain_map", domain_map)
        self.repository.save_domain_map(session_id, domain_map)
        return domain_map

    @staticmethod
    def _is_duplicate(
        candidate: ProblemCandidate, existing: list[ProblemCandidate]
    ) -> bool:
        text = f"{candidate.title} {candidate.description}"
        for other in existing:
            other_text = f"{other.title} {other.description}"
            if similarity(text, other_text) > 0.72:
                return True
        return False
