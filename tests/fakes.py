"""Deterministic test doubles.

These are used only in tests. Production always uses OllamaClient and the real
research connectors.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from src.agents.adversarial_critic import (
    CriticismLLM,
    CritiqueLLM,
    RebuttalItemLLM,
    RebuttalLLM,
    SelectionLLM,
    VerdictLLM,
)
from src.agents.domain_discovery import (
    DomainListLLM,
    DomainLLM,
    ProblemListLLM,
    ProblemLLM,
)
from src.agents.hackathon_intelligence import (
    CriterionLLM,
    HackathonIntelLLM,
    OrganizerLLM,
    ScoutLLM,
)
from src.agents.innovation_research import ExistingSolutionLLM, GapLLM
from src.agents.solution_architect import RequirementLLM, RiskLLM, SolutionLLM
from src.evaluation.rubric import CriterionScoreLLM, EvaluationLLM, GateLLM
from src.models.intelligence import IntelligenceContext
from src.models.research import GitHubProject
from src.research.base import PageContent, SearchResult
from src.research.registry import SearchBundle


class FakeLLM:
    """Returns schema-appropriate deterministic responses."""

    def __init__(self, score: float = 8.0, force_reject_all: bool = False) -> None:
        self.score = score
        self.force_reject_all = force_reject_all
        self.calls: list[str] = []
        self.stats = _Stats()

    def model_name(self) -> str:
        return "fake-model"

    def generate_text(
        self, prompt: str, system: str | None = None, temperature=None
    ) -> str:
        return "deterministic text"

    def generate_json(
        self, prompt: str, schema: type[BaseModel], system=None, temperature=None
    ):
        name = schema.__name__
        self.calls.append(name)
        if name == "ScoutLLM":
            return ScoutLLM(
                organizer_name="Example Foundation",
                official_theme="Sustainable cities",
                additional_search_queries=["Example Foundation sustainability goals"],
            )
        if name == "HackathonIntelLLM":
            return HackathonIntelLLM(
                organizer=OrganizerLLM(
                    name="Example Foundation",
                    mission="Improve urban sustainability",
                    ideology="Public-interest technology",
                    objectives=["Fund practical civic innovation"],
                    confidence=0.7,
                ),
                judging_criteria=[
                    CriterionLLM(
                        criterion="Impact", weight=30, description="Real-world impact"
                    )
                ],
                submission_requirements=["Working demo", "Source code"],
                technical_restrictions=["Open-source dependencies"],
                organizer_goals=["Fund practical civic innovation"],
                recurring_priorities=["Measurable urban impact"],
                verified_facts=["Organiser runs a sustainability programme"],
                assumptions=["Judging weights are inferred"],
                confidence=0.7,
            )
        if name == "DomainListLLM":
            return DomainListLLM(
                reasoning="Theme connects urban systems and public health.",
                domains=[
                    DomainLLM(
                        name="Urban mobility",
                        description="Movement of people and goods in cities",
                        relevance_type="primary",
                        relevance_explanation="Directly affects emissions and access.",
                        subdomains=["public transport", "cycling"],
                        connections_to_theme=["lower urban emissions"],
                        interdisciplinary_links=["public health", "economics"],
                        search_queries=["urban mobility emissions evidence"],
                        confidence=0.8,
                    ),
                    DomainLLM(
                        name="Urban public health",
                        description="Health outcomes in dense populations",
                        relevance_type="interdisciplinary",
                        relevance_explanation="Transport and green space affect health.",
                        subdomains=["air quality", "heat exposure"],
                        connections_to_theme=["inclusive urban life"],
                        interdisciplinary_links=["climate science"],
                        search_queries=["urban heat health evidence"],
                        confidence=0.7,
                    ),
                    DomainLLM(
                        name="Municipal waste systems",
                        description="Collection and recovery of urban waste",
                        relevance_type="secondary",
                        relevance_explanation="Waste is a major urban sustainability gap.",
                        subdomains=["recycling", "organic waste"],
                        connections_to_theme=["sustainable cities"],
                        interdisciplinary_links=["circular economy"],
                        search_queries=["municipal waste recycling evidence"],
                        confidence=0.7,
                    ),
                ],
            )
        if name == "ProblemListLLM":
            if "Urban public health" in prompt:
                return ProblemListLLM(
                    problems=[
                        ProblemLLM(
                            title="Heat-vulnerable residents lack local early-warning guidance",
                            description=(
                                "Older residents and outdoor workers lack street-level "
                                "heat warnings that reflect their immediate environment."
                            ),
                            subdomain="heat exposure",
                            affected_people=["older residents", "outdoor workers"],
                            seriousness="high",
                            evidence_indices=[1, 3],
                            inadequate_solutions=["City-wide heat alerts"],
                            overlooked_needs=["Block-level heat guidance"],
                            emerging_opportunities=["Urban heat models"],
                            future_potential=["Personal heat-risk coaching"],
                            theme_connection="Links climate adaptation and public health.",
                            is_generic=False,
                            confidence=0.72,
                        )
                    ]
                )
            if "Municipal waste" in prompt:
                return ProblemListLLM(
                    problems=[
                        ProblemLLM(
                            title="Recycling contamination is invisible to small municipalities",
                            description=(
                                "Small municipalities cannot afford contamination audits, "
                                "so recyclable material is lost to mixed waste."
                            ),
                            subdomain="recycling",
                            affected_people=["municipal waste teams", "residents"],
                            seriousness="moderate",
                            evidence_indices=[1, 3],
                            inadequate_solutions=["Manual spot checks"],
                            overlooked_needs=["Low-cost contamination detection"],
                            emerging_opportunities=[
                                "Computer vision on collection vehicles"
                            ],
                            future_potential=["Pay-as-you-throw feedback"],
                            theme_connection="Improves urban circularity.",
                            is_generic=False,
                            confidence=0.65,
                        )
                    ]
                )
            return ProblemListLLM(
                problems=[
                    ProblemLLM(
                        title="Residents cannot identify safe low-pollution commute routes",
                        description=(
                            "Daily commuters lack street-level pollution information, "
                            "so they cannot choose routes that reduce exposure."
                        ),
                        subdomain="air quality",
                        affected_people=["commuters", "cyclists", "asthma patients"],
                        seriousness="high",
                        evidence_indices=[1, 2],
                        inadequate_solutions=["Static air-quality dashboards"],
                        overlooked_needs=["Route-level exposure guidance"],
                        emerging_opportunities=["Low-cost sensor networks"],
                        future_potential=["Personalised exposure-aware navigation"],
                        theme_connection="Directly links mobility, health and sustainability.",
                        is_generic=False,
                        confidence=0.75,
                    )
                ]
            )
        if name == "GapLLM":
            return GapLLM(
                classification="potentially_differentiated_opportunity",
                gap_description=(
                    "Existing dashboards report city-wide averages, not personalised "
                    "street-level route exposure."
                ),
                differentiation_potential=(
                    "Street-level routing plus explainable exposure estimates."
                ),
                evidence_summary="Two credible sources and one open-source dashboard.",
                existing_solutions=[
                    ExistingSolutionLLM(
                        evidence_index=1,
                        name="City air quality dashboard",
                        solution_type="open_source",
                        description="Reports city-wide AQI.",
                        what_it_solves="Awareness of general pollution levels.",
                        target_users=["citizens"],
                        technologies=["Python"],
                        disadvantages=["No route-level guidance"],
                        unsolved_aspects=["Personal exposure"],
                        missing_features=["Routing"],
                        adoption_barriers=["Static data"],
                    )
                ],
                confidence=0.7,
            )
        if name == "SolutionLLM":
            return SolutionLLM(
                title="Exposure-aware commute coach",
                proposed_solution=(
                    "A mobile-friendly planner that combines street-level pollution "
                    "estimates with routing to recommend lower-exposure commutes."
                ),
                target_users=["commuters", "cyclists", "public health teams"],
                user_pain_point="No practical way to compare route exposure.",
                unique_differentiation=(
                    "Personalised route-level exposure guidance with explainable "
                    "trade-offs between time, pollution and accessibility."
                ),
                relevant_technologies=["Python", "Streamlit", "open data", "routing"],
                data_requirements=[
                    RequirementLLM(
                        category="data",
                        description="Open street network and air-quality sensors",
                        availability="available",
                        cost="free",
                        risk_level="medium",
                    )
                ],
                api_requirements=[
                    RequirementLLM(
                        category="api",
                        description="Open routing API",
                        availability="limited",
                        cost="free",
                        risk_level="medium",
                    )
                ],
                technical_architecture=(
                    "Ingestion -> exposure grid -> route scorer -> Streamlit demo."
                ),
                development_complexity="medium",
                estimated_hours=20,
                infrastructure_requirements=["Laptop"],
                estimated_cost="minimal",
                dependencies=["Open data"],
                risks=[
                    RiskLLM(
                        risk_type="data",
                        description="Sensor coverage is uneven.",
                        severity="medium",
                        likelihood="likely",
                        mitigation="Show confidence intervals and fall back to models.",
                    ),
                    RiskLLM(
                        risk_type="technical",
                        description="Routing API limits.",
                        severity="low",
                        likelihood="possible",
                        mitigation="Cache routes for the demo.",
                    ),
                ],
                advantages=["Clear demo", "Evidence-backed"],
                disadvantages=["Depends on open data quality"],
                mitigation_strategies=["Pre-cache demo routes"],
                hackathon_demo_plan="Show two routes and the exposure difference.",
                should_reject=False,
                feasibility_confidence=0.8,
            )
        if name == "EvaluationLLM":
            criteria = [
                "Real-world problem significance",
                "Originality and differentiation",
                "Technical feasibility",
                "Hackathon theme relevance",
                "Organizer and sponsor alignment",
                "Innovation and future potential",
                "Implementation within deadline",
                "Demonstration and judging appeal",
            ]
            return EvaluationLLM(
                scores=[
                    CriterionScoreLLM(
                        name=criterion,
                        score=self.score,
                        justification="Grounded in the supplied evidence.",
                        evidence=["test evidence"],
                    )
                    for criterion in criteria
                ],
                gates=[
                    GateLLM(
                        name=gate,
                        status="passed",
                        justification="Checked by the deterministic gate.",
                    )
                    for gate in [
                        "Credible evidence of the problem",
                        "Existing-solution investigation",
                        "Honest originality classification",
                        "Practical implementation path",
                        "Realistic hackathon deadline",
                        "Risk and disadvantage assessment",
                        "Compliance with hackathon rules",
                    ]
                ],
                overall_assessment="Strong but not perfect.",
                strengths=["Specific users", "Clear evidence"],
                weaknesses=["Data quality risk"],
            )
        if name == "CritiqueLLM":
            return CritiqueLLM(
                criticisms=[
                    CriticismLLM(
                        issue="Is the differentiation materially different from a dashboard?",
                        category="originality",
                        severity="major",
                        why_it_matters="Judges may see another AQI app.",
                        evidence_needed="Show route-level capability.",
                        evidence_query="route level air quality exposure",
                    )
                ],
                generic_risk="Medium",
                verdict="mixed",
                summary="Needs sharper differentiation.",
            )
        if name == "RebuttalLLM":
            return RebuttalLLM(
                rebuttals=[
                    RebuttalItemLLM(
                        issue="Is the differentiation materially different from a dashboard?",
                        response="The evidence supports route-level scoring, not just reporting.",
                        evidence_indices=[1],
                        resolved=True,
                        residual_risk="Demo must show the routing clearly.",
                    )
                ],
                revised_differentiation="Route-level, explainable exposure trade-offs.",
                new_risks=["Sensor sparsity"],
                recommendation="advance",
            )
        if name == "VerdictLLM":
            return VerdictLLM(
                resolved_count=1,
                unresolved_critical=0,
                score_adjustment=0,
                recommendation="advance",
                summary="Material criticism was answered with evidence.",
                evidence_quality="adequate",
            )
        if name == "SelectionLLM":
            return SelectionLLM(
                winner_label="" if self.force_reject_all else "A",
                runner_up_labels=[],
                reject_all=self.force_reject_all,
                rationale=(
                    "All candidates rejected in test mode."
                    if self.force_reject_all
                    else "Candidate A has the strongest evidence and demo path."
                ),
                confidence=0.7,
            )
        if name == "StructuredHackathonDoc":
            from src.knowledge.document_intelligence.models import (
                ExtractedTrack,
                ProvenancedField,
                ProvenancedItem,
                StructuredHackathonDoc,
            )
            return StructuredHackathonDoc(
                hackathon_name="Kerala Civic Challenge 2026",
                organizer="Kerala State Planning Board",
                official_website="https://kcc.kerala.gov.in",
                theme="Resilient Coastal Infrastructure",
                tracks=["Estuarine Water Management", "Decentralized Healthcare"],
                extracted_tracks=[
                    ExtractedTrack(name="Estuarine Water Management", description="Polder and saline management"),
                    ExtractedTrack(name="Decentralized Healthcare", description="Rural clinic triage"),
                ],
                judging_criteria=["Technical Feasibility 30%", "Local Relevance 30%"],
                technical_restrictions=["No paid APIs", "Offline first"],
                submission_deadline="2026-11-30",
                event_duration="36 hours",
                provenanced_fields={
                    "hackathon_name": ProvenancedField(value="Kerala Civic Challenge 2026", filename="test.pdf", page=1, confidence=0.95),
                    "theme": ProvenancedField(value="Resilient Coastal Infrastructure", filename="test.pdf", page=1, confidence=0.95),
                    "organizer": ProvenancedField(value="Kerala State Planning Board", filename="test.pdf", page=1, confidence=0.90),
                    "submission_deadline": ProvenancedField(value="2026-11-30", filename="test.pdf", page=1, confidence=0.90),
                },
                provenanced_items={
                    "judging_criteria": [ProvenancedItem(text="Technical Feasibility 30%", filename="test.pdf", page=1)],
                    "technical_restrictions": [ProvenancedItem(text="No paid APIs", filename="test.pdf", page=1)],
                },
                extracted_facts=["Event organized by Kerala State Planning Board.", "Requires offline operation."],
            )
        if name == "StructuredResearchDoc":
            from src.knowledge.document_intelligence.models import (
                ProvenancedField,
                ProvenancedItem,
                StructuredResearchDoc,
            )
            return StructuredResearchDoc(
                document_title="Canopy Density in Kerala Agro-Ecosystems",
                authors_or_institution="Kerala Agricultural University",
                target_geography="Kuttanad, Kerala",
                key_findings=["Agro-ecological canopy density varies significantly across polders."],
                problems_identified=["Saline intrusion in Kuttanad paddy fields causes 40% yield drop."],
                datasets_and_methodologies=["Bhoonidhi multi-spectral satellite imagery"],
                technical_feasibility_insights=["Offline inference on edge microcontrollers achievable"],
                provenanced_fields={
                    "document_title": ProvenancedField(value="Canopy Density in Kerala Agro-Ecosystems", filename="test.pdf", page=1),
                    "target_geography": ProvenancedField(value="Kuttanad, Kerala", filename="test.pdf", page=1),
                },
                provenanced_items={
                    "problems_identified": [ProvenancedItem(text="Saline intrusion in Kuttanad paddy fields causes 40% yield drop.", filename="test.pdf", page=1)],
                },
                extracted_facts=["40% crop yield drop recorded due to seasonal salinity."],
            )
        raise AssertionError(f"FakeLLM has no response for schema {name}")


class _Stats:
    calls = 0
    failures = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "calls": 0,
            "failures": 0,
            "prompt_chars": 0,
            "response_chars": 0,
            "total_seconds": 0,
            "by_agent": {},
        }


class FakeResearch:
    """Deterministic research facade with real-looking provenance URLs."""

    def __init__(self, empty: bool = False) -> None:
        self.empty = empty
        self.queries: list[str] = []

    def _results(self) -> list[SearchResult]:
        if self.empty:
            return []
        return [
            SearchResult(
                title="Street-level air pollution exposure study",
                url="https://example.org/paper-air-quality",
                snippet="Commuter exposure varies substantially by route.",
                source_type="openalex",
                reliability=0.86,
                published_at=datetime(2025, 1, 1, tzinfo=UTC),
            ),
            SearchResult(
                title="City air quality dashboard",
                url="https://github.com/example/aqi-dashboard",
                snippet="An open-source city-wide AQI dashboard.",
                source_type="github",
                reliability=0.8,
                metadata={
                    "stars": 120,
                    "forks": 12,
                    "language": "Python",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "topics": ["air-quality"],
                    "archived": False,
                    "description": "City dashboard",
                },
            ),
            SearchResult(
                title="Waste contamination audit study",
                url="https://example.org/paper-waste",
                snippet="Contamination reduces recycling recovery.",
                source_type="arxiv",
                reliability=0.8,
            ),
        ]

    def search(self, session_id, query, source_types=None, limit=None) -> SearchBundle:
        self.queries.append(query)
        bundle = SearchBundle(query=query, results=self._results())
        return bundle

    def multi_search(
        self, session_id, queries, source_types=None, limit=6, max_results=30
    ) -> SearchBundle:
        self.queries.extend(queries)
        bundle = SearchBundle(query="; ".join(queries), results=self._results())
        bundle.dedupe()
        return bundle

    def fetch_page(self, session_id, url) -> PageContent:
        return PageContent(
            url=url,
            final_url=url,
            title="Official hackathon page",
            text="A sustainable cities hackathon focused on practical civic innovation.",
        )

    def github_projects(self, session_id, query, limit=8) -> list[GitHubProject]:
        return [
            GitHubProject(
                url="https://github.com/example/aqi-dashboard",
                name="example/aqi-dashboard",
                description="City-wide AQI dashboard",
                stars=120,
                forks=12,
                language="Python",
                is_active=True,
            )
        ]


class FakeIntelligence:
    """No-op Continuous Intelligence for offline integration tests."""

    def context_for_theme(
        self, theme, extra_terms=None, limit=20
    ) -> IntelligenceContext:
        return IntelligenceContext(note="Fake intelligence: no stored signals.")

    def context_as_prompt(self, context, max_items=10) -> str:
        return ""
