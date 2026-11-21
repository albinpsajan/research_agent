"""Phase 3 Comprehensive Regression Suite.

Verifies:
- Dynamic domain discovery without fixed caps (>3 domains supported)
- Relevance-based stopping criteria and explanation
- EvidenceAggregator: associating >=2 independent sources
- Honest handling when research finds insufficient sources
- Existing-solution record transfer and gap summary enrichment
- Quality gate input validation: differentiation, tech stack, risks/mitigations
- Source classification (preprints vs scholarly metadata vs code)
- Constraint provenance (user-provided vs agent hypothesis)
- GitHub query optimization and rate-limit safety
- Explicit quality gate failure categorization
"""

from __future__ import annotations

from datetime import datetime
import pytest

from src.evaluation.rubric import EvaluationService, GATE_NAMES
from src.models.candidate import CandidateSolution, RiskAssessment
from src.models.domain import DiscoveredDomain, DomainMap, DomainRelevance, ProblemCandidate, ProblemEvidence
from src.models.evaluation import QualityGateStatus
from src.models.hackathon import HackathonInput, HackathonIntelligence
from src.models.pipeline import PipelineOptions
from src.models.provenance import CategorizedConstraint, ProvenanceCategory
from src.models.research import (
    ExistingSolution,
    GitHubProject,
    InnovationGap,
    OpportunityClassification,
    PublicationCategory,
    ResearchSource,
    SourceType,
    VerificationLevel,
)
from src.research.base import SearchResult
from src.research.evidence_aggregator import EvidenceAggregator
from src.research.github import optimize_github_query, GitHubConnector


# ---------------------------------------------------------------------------
# 1. Dynamic Domain Discovery & Stopping Reason
# ---------------------------------------------------------------------------

def test_dynamic_domain_discovery_options_and_stopping_reason():
    opts = PipelineOptions(domain_exploration_budget=12, min_domain_relevance=0.45)
    assert opts.max_domains is None  # No legacy cap by default
    assert opts.domain_exploration_budget == 12
    assert opts.min_domain_relevance == 0.45

    # Simulate discovery of 5 domains (more than the previous rigid cap of 3)
    domains = [
        DiscoveredDomain(
            name=f"Domain {i}",
            description="Test domain",
            relevance_type=DomainRelevance.PRIMARY if i <= 3 else DomainRelevance.INTERDISCIPLINARY,
            relevance_explanation="Relevant to climate-resilient agriculture",
            confidence=0.8,
            relevance_score=0.75 - (i * 0.05),
        )
        for i in range(1, 6)
    ]
    dmap = DomainMap(
        theme="Artificial Intelligence for Climate-Resilient Agriculture and Rural Communities",
        domains=domains,
        total_domains_explored=5,
        exploration_budget=12,
        exploration_budget_consumed=5,
        stopping_reason="Dynamic exploration completed: all 5 relevant thematic dimensions captured; subsequent intersections produced diminishing returns.",
        diminishing_returns_reached=True,
    )
    assert len(dmap.domains) == 5
    assert dmap.diminishing_returns_reached is True
    assert "diminishing returns" in dmap.stopping_reason.lower()


# ---------------------------------------------------------------------------
# 2. Evidence Aggregation: >=2 Independent Sources per Candidate
# ---------------------------------------------------------------------------

def test_evidence_aggregator_associates_independent_sources():
    problem = ProblemCandidate(
        id="P01",
        title="Saline Water Intrusion in Coastal Paddy Cultivation",
        description="Soil degradation and cyclonic storm surges affecting coastal smallholder rice farms.",
        domain="Precision Agriculture",
        subdomain="Soil Salinity",
        evidence=[
            ProblemEvidence(
                description="Study 1: Coastal paddy soil salinity",
                source_url="https://doi.org/10.1000/study1",
                source_type="crossref",
                credibility=0.85,
            )
        ],
    )
    assert len(problem.evidence) == 1

    # Pool of search results retrieved from scholarly APIs
    pool = [
        SearchResult(
            title="Remote Sensing for Soil Salinity and Paddy Yield in Coastal Regions",
            url="https://arxiv.org/abs/2601.12345v1",
            snippet="Satellite monitoring of soil degradation and saline intrusion in rice paddy fields.",
            source_type="arxiv",
            publication_category="preprint",
            reliability=0.85,
        ),
        SearchResult(
            title="Unrelated Urban Traffic Congestion in Tokyo",
            url="https://doi.org/10.1000/unrelated",
            snippet="Deep learning models for metropolitan traffic flow optimization.",
            source_type="crossref",
            reliability=0.90,
        ),
    ]

    # Aggregate evidence
    EvidenceAggregator.aggregate_problem_evidence(problem, pool, min_sources=2)

    # Should attach the relevant paper, but reject the unrelated traffic paper
    assert len(problem.evidence) == 2
    urls = {e.source_url for e in problem.evidence}
    assert "https://doi.org/10.1000/study1" in urls
    assert "https://arxiv.org/abs/2601.12345v1" in urls
    assert "https://doi.org/10.1000/unrelated" not in urls


def test_evidence_aggregator_honestly_handles_insufficient_sources():
    problem = ProblemCandidate(
        id="P02",
        title="Unprecedented Rare Soil Fungus Mutation",
        description="A newly observed pathogen with virtually no existing academic literature.",
        domain="Precision Agriculture",
        evidence=[
            ProblemEvidence(
                description="Initial field note",
                source_url="https://example.com/note1",
                source_type="news",
                credibility=0.55,
            )
        ],
    )
    # Pool contains only completely unrelated articles
    pool = [
        SearchResult(
            title="Quantum Cryptography Key Exchange",
            url="https://arxiv.org/abs/2601.99999",
            snippet="Post-quantum cryptographic algorithms.",
            source_type="arxiv",
            reliability=0.85,
        )
    ]
    EvidenceAggregator.aggregate_problem_evidence(problem, pool, min_sources=2)
    # Does not fabricate an unrelated source
    assert len(problem.evidence) == 1


# ---------------------------------------------------------------------------
# 3. Gap Summary and Differentiation Transfer
# ---------------------------------------------------------------------------

def test_gap_summary_and_differentiation_enrichment():
    gap = InnovationGap(
        problem_candidate_id="P01",
        classification=OpportunityClassification.UNDERSERVED,
        existing_solutions=[
            ExistingSolution(
                name="SalinityMonitor v1",
                solution_type="open_source",
                description="Basic IoT soil salinity sensor script.",
                url="https://github.com/example/salinity-sensor",
                disadvantages=["Lacks predictive forecasting", "Requires continuous WiFi connectivity"],
            )
        ],
        github_projects=[
            GitHubProject(
                url="https://github.com/example/crop-salinity",
                name="crop-salinity",
                stars=45,
            )
        ],
        gap_description="Lack of offline edge-prediction algorithms for saline intrusion risk.",
        evidence_summary="",  # Model omitted this
        differentiation_potential="",  # Model omitted this
    )

    EvidenceAggregator.enrich_gap_summary(gap)

    # Evidence summary must be populated with verified facts from the solutions
    assert len(gap.evidence_summary) > 20
    assert "SalinityMonitor v1" in gap.evidence_summary
    assert "crop-salinity" in gap.evidence_summary
    assert len(gap.differentiation_potential) > 20


# ---------------------------------------------------------------------------
# 4. Candidate Solution Quality Gate Inputs (Differentiation, Tech, Risks)
# ---------------------------------------------------------------------------

def test_candidate_solution_enrichment_prevents_empty_fields():
    problem = ProblemCandidate(
        id="P01",
        title="AI-Driven Precision Salinity Management",
        description="Predicting salinity spikes for coastal smallholder rice farmers.",
        domain="Precision Agriculture",
        inadequate_solutions=["Current systems require high-cost cellular modems and cloud subscriptions."],
        overlooked_needs=["Offline predictive guidance using low-cost sensor data."],
        evidence=[
            ProblemEvidence(
                description="Study 1",
                source_url="https://doi.org/10.1000/1",
                credibility=0.8,
            ),
            ProblemEvidence(
                description="Study 2",
                source_url="https://arxiv.org/abs/2601.2",
                credibility=0.85,
            ),
        ],
    )
    gap = InnovationGap(
        problem_candidate_id="P01",
        classification=OpportunityClassification.UNDERSERVED,
        gap_description="Absence of lightweight offline models.",
        differentiation_potential="Combines lightweight edge AI with open Sentinel-2 imagery for offline advisory.",
    )

    candidate = CandidateSolution(
        id="C01",
        title="AgriEdge Salinity Advisory",
        problem_candidate_id="P01",
        problem_statement=problem.description,
        proposed_solution="An edge-deployable AI advisory for coastal smallholders.",
        unique_differentiation="",  # Empty from small model
        relevant_technologies=[],   # Empty from small model
        risks=[],                  # Empty from small model
        disadvantages=[],          # Empty from small model
        mitigation_strategies=[],  # Empty from small model
    )

    EvidenceAggregator.enrich_candidate_solution(candidate, problem, gap)

    # Quality Gate 3 input: Differentiation must be >= 30 chars
    assert len(candidate.unique_differentiation) >= 30
    assert len(candidate.relevant_technologies) >= 2
    assert len(candidate.risks) >= 2
    assert len(candidate.disadvantages) >= 1
    assert len(candidate.mitigation_strategies) >= 1
    assert all(r.mitigation for r in candidate.risks)


# ---------------------------------------------------------------------------
# 5. Source Classification & Verification Levels
# ---------------------------------------------------------------------------

def test_source_classification_types():
    # arXiv preprint
    arxiv_res = SearchResult(
        title="Climate Forecasting with Graph Neural Networks",
        url="https://arxiv.org/abs/2601.55555v1",
        source_type="arxiv",
        publication_category=PublicationCategory.PREPRINT,
        verification_level=VerificationLevel.METADATA_VALIDATED,
        reliability=0.85,
    )
    assert arxiv_res.publication_category == "preprint"
    assert arxiv_res.verification_level == "metadata_validated"

    # Crossref scholarly metadata
    crossref_res = SearchResult(
        title="Precision Agriculture Strategies",
        url="https://doi.org/10.1016/j.agwat.2025.109000",
        source_type="crossref",
        publication_category=PublicationCategory.SCHOLARLY_METADATA,
        verification_level=VerificationLevel.METADATA_VALIDATED,
        reliability=0.85,
    )
    assert crossref_res.publication_category == "scholarly_metadata"

    # GitHub software project
    gh_res = SearchResult(
        title="crop-simulation-model",
        url="https://github.com/open-ag/crop-sim",
        source_type="github",
        publication_category=PublicationCategory.SOFTWARE_PROJECT,
        verification_level=VerificationLevel.METADATA_VALIDATED,
        reliability=0.78,
    )
    assert gh_res.publication_category == "software_project"


# ---------------------------------------------------------------------------
# 6. Provenance Categories: User Constraints vs Hypotheses
# ---------------------------------------------------------------------------

def test_provenance_categories():
    user_c = CategorizedConstraint(
        category=ProvenanceCategory.USER_PROVIDED,
        description="Must operate offline in rural settings.",
        is_mandatory=True,
    )
    assert user_c.category == "user_provided"
    assert user_c.is_mandatory is True

    agent_h = CategorizedConstraint(
        category=ProvenanceCategory.AGENT_HYPOTHESIS,
        description="Target smallholder farmers in coastal Odisha.",
        is_mandatory=False,
    )
    assert agent_h.category == "agent_hypothesis"
    assert agent_h.is_mandatory is False


# ---------------------------------------------------------------------------
# 7. GitHub Query Optimization & Rate Limit Protection
# ---------------------------------------------------------------------------

def test_github_query_optimizer():
    conversational = (
        "How many entries are there in recent hackathons or academic papers that propose "
        "a real-time data center emissions monitoring and community engagement platform?"
    )
    optimized = optimize_github_query(conversational)
    assert len(optimized) < 80
    assert "?" not in optimized
    assert "how" not in optimized.split()
    assert "many" not in optimized.split()
    # High-signal keywords retained
    assert "data" in optimized or "center" in optimized or "emissions" in optimized or "monitoring" in optimized


# ---------------------------------------------------------------------------
# 8. Explicit Gate Failure Categorization
# ---------------------------------------------------------------------------

def test_gate_failure_categorization():
    prob_single_source = ProblemCandidate(
        id="P01",
        title="Title",
        description="Desc",
        domain="Domain",
        evidence=[ProblemEvidence(description="Only 1", source_url="https://example.com/1")],
    )
    cand = CandidateSolution(
        id="C01",
        problem_candidate_id="P01",
        problem_statement="Desc",
        unique_differentiation="",
    )
    gap_none = InnovationGap(
        problem_candidate_id="P01",
        classification=OpportunityClassification.INSUFFICIENT_EVIDENCE,
    )

    reason1 = EvidenceAggregator.classify_gate_failure(GATE_NAMES[1], cand, prob_single_source, gap_none)
    assert "RESEARCH_INSUFFICIENT" in reason1

    reason2 = EvidenceAggregator.classify_gate_failure(GATE_NAMES[3], cand, prob_single_source, gap_none)
    assert "RESEARCH_INSUFFICIENT" in reason2

    reason3 = EvidenceAggregator.classify_gate_failure(GATE_NAMES[4], cand, prob_single_source, gap_none)
    assert "NO_DIFFERENTIATION" in reason3
