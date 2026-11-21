"""Agent 1 — Hackathon Intelligence Agent."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from config.logging_config import get_logger
from src.agents.base import BaseAgent, allowed_urls, sanitize_model_urls
from src.models.hackathon import (
    HackathonInput,
    HackathonIntelligence,
    JudgeProfile,
    JudgingCriteria,
    OrganizerProfile,
    PreviousProject,
    SponsorProfile,
)
from src.models.provenance import CategorizedConstraint, ProvenanceCategory
from src.knowledge.hackathon_playbook import HackathonPlaybookService
from src.knowledge.document_intelligence.service import DocumentIntelligenceService
from src.research.base import ResearchError
from src.research.registry import SearchBundle

logger = get_logger("agents.hackathon_intelligence")

SYSTEM = """You are the Hackathon Intelligence Agent for HackathonIQ.
Your job is to understand what the organisers are actually trying to achieve.
Rules:
- Use ONLY the supplied evidence. Never invent a fact, statistic, judge, sponsor,
  previous project, winner, URL, criterion or deadline.
- Separate verified facts (directly supported by evidence) from assumptions.
- If evidence is thin, say so in assumptions and lower confidence.
- Return JSON only, exactly matching the requested schema.
"""


class OrganizerLLM(BaseModel):
    name: str = ""
    mission: str = ""
    ideology: str = ""
    objectives: list[str] = Field(default_factory=list)
    website: str | None = None
    source_urls: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.4, ge=0, le=1)

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: Any) -> Any:
        if isinstance(v, (int, float)) and v > 1:
            return min(1.0, v / 100.0)
        return v


class JudgeLLM(BaseModel):
    name: str
    expertise: list[str] = Field(default_factory=list)
    organization: str | None = None
    source_url: str | None = None


class SponsorLLM(BaseModel):
    name: str
    interests: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    initiatives: list[str] = Field(default_factory=list)
    source_url: str | None = None


class PreviousProjectLLM(BaseModel):
    title: str
    description: str = ""
    year: int | None = None
    placement: str | None = None
    technologies: list[str] = Field(default_factory=list)
    source_url: str | None = None


class CriterionLLM(BaseModel):
    criterion: str
    weight: float | None = None
    description: str = ""


class ScoutLLM(BaseModel):
    organizer_name: str = ""
    official_theme: str = ""
    additional_search_queries: list[str] = Field(default_factory=list, max_length=6)


class HackathonIntelLLM(BaseModel):
    organizer: OrganizerLLM = Field(default_factory=OrganizerLLM)
    judges: list[JudgeLLM] = Field(default_factory=list)
    sponsors: list[SponsorLLM] = Field(default_factory=list)
    previous_projects: list[PreviousProjectLLM] = Field(default_factory=list)
    judging_criteria: list[CriterionLLM] = Field(default_factory=list)
    submission_requirements: list[str] = Field(default_factory=list)
    technical_restrictions: list[str] = Field(default_factory=list)
    time_limit_hours: float | None = None
    target_participants: str = ""
    expected_outcomes: list[str] = Field(default_factory=list)
    organizer_goals: list[str] = Field(default_factory=list)
    recurring_priorities: list[str] = Field(default_factory=list)
    verified_facts: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.4, ge=0, le=1)

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: Any) -> Any:
        if isinstance(v, (int, float)) and v > 1:
            return min(1.0, v / 100.0)
        return v


class HackathonIntelligenceAgent(BaseAgent):
    """Researches organisers, judges, sponsors, past editions and expectations."""

    name = "hackathon_intelligence"
    description = "Understands the hackathon and what its organisers actually want"

    def run(
        self,
        session_id: str,
        hackathon: HackathonInput,
        *,
        intelligence_context: str = "",
    ) -> HackathonIntelligence:
        bundle = SearchBundle(query=hackathon.theme)
        official_texts: list[str] = []
        page_urls: list[str] = []
        fetch_notes: list[str] = []

        for label, url in (
            ("official website", hackathon.website_url),
            ("rules page", hackathon.rules_url),
        ):
            if not url or url.startswith("doc://"):
                continue
            try:
                page = self.research.fetch_page(session_id, url)
                page_urls.extend([url, page.final_url])
                official_texts.append(
                    f"--- {label.upper()}: {page.final_url} ---\n"
                    f"TITLE: {page.title}\n{page.text[:7000]}"
                )
            except ResearchError as exc:
                fetch_notes.append(f"Could not retrieve {label} ({url}): {exc}")
                logger.warning("Failed to fetch %s: %s", url, exc)

        scout_prompt = f"""Hackathon theme: {hackathon.theme}
Hackathon name: {hackathon.name or "not supplied"}
Official website: {hackathon.website_url or "not supplied"}
Constraints supplied by user: {hackathon.constraints or "none"}

Official page excerpts:
{chr(10).join(official_texts)[:8000] or "(none retrieved)"}

Identify the most likely organising institution and propose up to 6 concrete
search queries that would find the organiser's mission, previous editions,
previous winners, judges, sponsors, judging criteria and rules. Do not invent
facts; this is only a search plan."""
        try:
            scout = self.llm.generate_json(scout_prompt, ScoutLLM, SYSTEM)
        except Exception as exc:  # noqa: BLE001 - search can continue without scout
            logger.warning("Intelligence scout failed: %s", exc)
            scout = ScoutLLM()

        organizer_name = scout.organizer_name.strip()
        queries: list[str] = []
        if organizer_name:
            queries.extend(
                [
                    f"{organizer_name} mission goals",
                    f"{organizer_name} hackathon",
                ]
            )
        if hackathon.name:
            queries.extend(
                [
                    f"{hackathon.name} previous winners",
                    f"{hackathon.name} judging criteria",
                    f"{hackathon.name} sponsors",
                ]
            )
        queries.extend(scout.additional_search_queries)
        queries.append(f"{hackathon.theme} hackathon challenges organisers")
        queries = list(dict.fromkeys(q.strip() for q in queries if q.strip()))[:8]

        for query in queries:
            found = self.research.search(
                session_id,
                query,
                source_types=["wikipedia", "duckduckgo", "rss", "hackernews", "github"],
                limit=5,
            )
            bundle.extend(found)
        bundle.dedupe()
        bundle.results = bundle.results[:30]

        playbook = HackathonPlaybookService()
        playbook_entries = playbook.retrieve_for_intelligence(hackathon.theme)
        playbook_guidance = playbook.format_guidance_for_prompt(playbook_entries)

        doc_service = DocumentIntelligenceService(self.repository, self.llm)
        doc_hits = doc_service.search_evidence(
            query=f"{hackathon.theme} {hackathon.name or ''} rules judging criteria restrictions eligibility track",
            session_id=session_id,
            limit=6,
        )
        doc_evidence_lines: list[str] = [h.as_evidence_context(i) for i, h in enumerate(doc_hits, 1)]
        doc_citations: list[str] = [h.citation for h in doc_hits if h.citation]

        prompt = f"""Hackathon theme: {hackathon.theme}
Hackathon name: {hackathon.name or "not supplied"}
Official website: {hackathon.website_url or "not supplied"}
Rules URL: {hackathon.rules_url or "not supplied"}
Deadline: {hackathon.deadline.isoformat() if hackathon.deadline else "not supplied"}
User constraints: {hackathon.constraints or "none"}

{playbook_guidance}

UPLOADED OFFICIAL EVENT DOCUMENTS & EVIDENCE (High Priority - Ground Truth):
{chr(10).join(doc_evidence_lines) or "(no uploaded documents)"}

OFFICIAL PAGE EXCERPTS:
{chr(10).join(official_texts)[:9000] or "(none retrieved)"}

RETRIEVED EVIDENCE (cite only these URLs or uploaded documents):
{_evidence(bundle)}

RECENT CONTINUOUS INTELLIGENCE (may be irrelevant; use only if relevant):
{intelligence_context[:3000] or "(none)"}

FETCH NOTES: {fetch_notes or "none"}

Produce the Hackathon Intelligence Report. Determine:
1. The organiser's real mission, ideology, objectives and recurring priorities.
2. Official theme, judging criteria, submission requirements and restrictions.
3. Previous editions, winners/finalists, judges and sponsors only where evidenced.
4. What the organiser is ACTUALLY trying to achieve beyond the theme wording.
5. What is verified versus assumed. Include explicit assumptions when evidence is thin.
Keep lists focused (max 8 items each). Do not invent URLs."""
        result = self.llm.generate_json(prompt, HackathonIntelLLM, SYSTEM)
        valid_external = [u for u in [hackathon.website_url, hackathon.rules_url] if u and not u.startswith("doc://")]
        allowed = allowed_urls(
            bundle, page_urls + valid_external + doc_citations
        )
        sanitize_model_urls(result, allowed)

        research_sources = [r.url for r in bundle.results if r.url]
        research_sources.extend(u for u in page_urls if u)
        research_sources.extend(doc_citations)
        research_sources = list(dict.fromkeys(research_sources))

        assumptions = list(result.assumptions)
        assumptions.extend(fetch_notes)
        if not result.verified_facts:
            assumptions.append(
                "No directly verifiable organiser facts were extracted; treat "
                "organiser intelligence as low-confidence."
            )

        has_doc_evidence = bool(doc_hits)
        categorized_constraints: list[CategorizedConstraint] = []
        if hackathon.constraints:
            for line in hackathon.constraints.splitlines():
                line = line.strip()
                if line:
                    categorized_constraints.append(
                        CategorizedConstraint(
                            category=ProvenanceCategory.USER_PROVIDED,
                            description=line,
                            is_mandatory=True,
                            source="user_input",
                        )
                    )
        for restriction in result.technical_restrictions:
            if restriction.strip():
                is_official = bool(hackathon.rules_url or hackathon.website_url or has_doc_evidence)
                cat = ProvenanceCategory.OFFICIAL_HACKATHON if is_official else ProvenanceCategory.AGENT_HYPOTHESIS
                categorized_constraints.append(
                    CategorizedConstraint(
                        category=cat,
                        description=restriction.strip(),
                        is_mandatory=is_official,
                        source="official_rules" if is_official else "agent_hypothesis",
                    )
                )

        has_specific_event = bool(hackathon.name or hackathon.website_url or hackathon.rules_url or has_doc_evidence)
        is_general_theme = not has_specific_event or not (result.organizer.name or organizer_name)
        if is_general_theme:
            assumptions.insert(
                0,
                "GENERAL THEME MODE: No specific organizer or sponsors were provided. Operating under theme-first mode; organizer and sponsor alignment is marked unassessable to ensure objective, uninvented research.",
            )

        organizer_profile = None
        if has_specific_event and (result.organizer.name or organizer_name):
            organizer_profile = OrganizerProfile(
                name=result.organizer.name or organizer_name or "Unknown organiser",
                mission=result.organizer.mission or None,
                ideology=result.organizer.ideology or None,
                objectives=result.organizer.objectives,
                website=result.organizer.website,
                source_urls=result.organizer.source_urls,
                confidence=result.organizer.confidence,
            )

        intelligence = HackathonIntelligence(
            hackathon_input=hackathon,
            organizer=organizer_profile,
            judges=[
                JudgeProfile(
                    name=j.name,
                    expertise=j.expertise,
                    organization=j.organization,
                    source_url=j.source_url,
                )
                for j in result.judges[:15]
            ],
            sponsors=[
                SponsorProfile(
                    name=s.name,
                    interests=s.interests,
                    technologies=s.technologies,
                    initiatives=s.initiatives,
                    source_url=s.source_url,
                )
                for s in result.sponsors[:15]
            ],
            previous_projects=[
                PreviousProject(
                    title=p.title,
                    description=p.description or None,
                    year=p.year,
                    placement=p.placement,
                    technologies=p.technologies,
                    source_url=p.source_url,
                )
                for p in result.previous_projects[:15]
            ],
            judging_criteria=[
                JudgingCriteria(
                    criterion=c.criterion,
                    weight=c.weight,
                    description=c.description or None,
                )
                for c in result.judging_criteria[:12]
            ],
            submission_requirements=result.submission_requirements[:12],
            technical_restrictions=result.technical_restrictions[:12],
            time_limit_hours=result.time_limit_hours,
            target_participants=result.target_participants or None,
            expected_outcomes=result.expected_outcomes[:10],
            organizer_goals=result.organizer_goals[:10],
            recurring_priorities=result.recurring_priorities[:10],
            categorized_constraints=categorized_constraints,
            verified_facts=result.verified_facts[:20],
            assumptions=assumptions[:20],
            research_sources=research_sources,
            is_general_theme_mode=is_general_theme,
        )
        self._save(session_id, "hackathon_intelligence", intelligence)
        return intelligence


def _evidence(bundle: SearchBundle) -> str:
    if not bundle.results:
        return "(no sources retrieved)"
    return "\n\n".join(
        r.as_context(i) for i, r in enumerate(bundle.results[:20], start=1)
    )
