"""Unit tests for Kerala and India Official Source Registry and Adaptation Models."""

from __future__ import annotations

from src.models.candidate import CandidateSolution
from src.models.research import (
    AdaptabilityClassification,
    GlobalToLocalAdaptation,
)
from src.research.evidence_aggregator import EvidenceAggregator
from src.research.sources import (
    KeralaIndiaSourceRegistry,
    SourceCoverageStatus,
)


def test_registry_catalog_and_coverage_summary():
    registry = KeralaIndiaSourceRegistry()
    summary = registry.get_coverage_summary()

    assert summary["total_official_sources"] >= 14
    assert summary["by_geography"]["kerala"] >= 5
    assert summary["by_geography"]["india"] >= 5
    assert summary["by_geography"]["global"] >= 4
    assert summary["by_status"][SourceCoverageStatus.INTEGRATED.value] >= 10


def test_recommend_sources_by_domain_agriculture():
    registry = KeralaIndiaSourceRegistry()
    recs = registry.recommend_sources("agriculture crop yield monsoon", geography="kerala", limit=4)

    assert len(recs) > 0
    rec_ids = [r.id for r in recs]
    # Should include KAU or DES ODR
    assert any(rid in {"KL-002", "KL-003"} for rid in rec_ids)


def test_recommend_sources_by_domain_disaster_and_landslides():
    registry = KeralaIndiaSourceRegistry()
    recs = registry.recommend_sources("landslides floods disaster risk", geography="kerala", limit=3)

    assert len(recs) > 0
    rec_names = [r.name for r in recs]
    # KSDMA should be top match
    assert any("KSDMA" in name or "Disaster" in name for name in rec_names)


def test_recommend_sources_satellite_and_earth_observation():
    registry = KeralaIndiaSourceRegistry()
    recs = registry.recommend_sources("satellite radar earth observation", geography="all", limit=5)

    assert len(recs) > 0
    authorities = [r.authority for r in recs]
    # Should recommend ISRO, Copernicus or NASA
    assert any("ISRO" in auth or "European Space Agency" in auth or "NASA" in auth for auth in authorities)


def test_generate_targeted_queries():
    registry = KeralaIndiaSourceRegistry()
    queries = registry.generate_targeted_queries("agroforestry climate", geography="kerala")

    assert len(queries) >= 3
    assert any("data.kerala.gov.in" in q for q in queries)
    assert any("kau.in" in q for q in queries)


def test_global_to_local_adaptation_five_tiers():
    tiers = [
        AdaptabilityClassification.TIER_A_DIRECT,
        AdaptabilityClassification.TIER_B_MODIFIED,
        AdaptabilityClassification.TIER_C_REDESIGN,
        AdaptabilityClassification.TIER_D_NON_TRANSFERABLE,
        AdaptabilityClassification.TIER_E_LOCALLY_ORIGINATED,
    ]
    assert len(tiers) == 5

    adaptation = GlobalToLocalAdaptation(
        global_reference_solution="FAO Agroforestry Suitability Model",
        global_source_url="https://www.fao.org/forestry/agroforestry",
        transferability_tier=AdaptabilityClassification.TIER_B_MODIFIED,
        kerala_applicability="Applicable to homestead agroforestry in Wayanad and Idukki districts.",
        india_scale_potential="Scalable to Western Ghats and northeastern hill regions across India.",
        required_modifications=[
            "Calibrate species envelope to humid-tropical monsoon patterns",
            "Malayalam vernacular advisory interface",
        ],
        local_constraints=[
            "High humidity and prolonged monsoon cloud cover",
            "Plot size < 0.5 ha",
        ],
    )

    assert adaptation.transferability_tier == AdaptabilityClassification.TIER_B_MODIFIED
    assert len(adaptation.required_modifications) == 2
    assert len(adaptation.local_constraints) == 2
    assert "Wayanad" in adaptation.kerala_applicability


def test_recommend_sources_healthcare_and_epidemiology():
    registry = KeralaIndiaSourceRegistry()
    recs = registry.recommend_sources("rural telemedicine dengue disease surveillance", geography="all", limit=5)

    assert len(recs) > 0
    rec_ids = [r.id for r in recs]
    # Should recommend DHS Kerala, ICMR, or WHO
    assert any(rid in {"KL-006", "IN-007", "GL-005"} for rid in rec_ids)


def test_recommend_sources_education_and_vernacular():
    registry = KeralaIndiaSourceRegistry()
    recs = registry.recommend_sources("vernacular education literacy public governance", geography="all", limit=5)

    assert len(recs) > 0
    rec_ids = [r.id for r in recs]
    # Should recommend UNESCO, UNICEF, Kerala Open Data, or MoSPI
    assert any(rid in {"GL-006", "GL-007", "KL-001", "IN-006"} for rid in rec_ids)


def test_verify_source_connectivity():
    registry = KeralaIndiaSourceRegistry()
    res = registry.verify_source_connectivity("KL-003")
    assert res["source_id"] == "KL-003"
    assert "KAU" in res["name"]
    assert res["is_configured"] is True

    unknown = registry.verify_source_connectivity("UNKNOWN-999")
    assert unknown["status"] == "unknown_source"
    assert unknown["is_configured"] is False


def test_candidate_solution_adaptation_dimensions_enrichment():
    cand = CandidateSolution(
        id="C01",
        problem_candidate_id="P01",
        problem_statement="Smallholders struggle with erratic rainfall in homestead plots.",
    )
    EvidenceAggregator.enrich_candidate_solution(cand)

    assert cand.kerala_adaptation is not None
    assert len(cand.kerala_evidence) >= 2
    assert len(cand.india_evidence) >= 2
    assert len(cand.global_comparisons) >= 2
    assert len(cand.existing_local_alternatives) >= 2
    assert len(cand.international_alternatives) >= 2
    assert len(cand.environmental_differences) >= 2
    assert len(cand.economic_differences) >= 2
    assert len(cand.cultural_considerations) >= 2
    assert len(cand.infrastructure_limitations) >= 2
    assert len(cand.regulatory_differences) >= 2
    assert len(cand.genuine_innovation_introduced) > 30


def test_all_five_adaptation_tiers_distinct_properties():
    tier_descriptions = {
        AdaptabilityClassification.TIER_A_DIRECT: "Direct transfer with parameter tuning",
        AdaptabilityClassification.TIER_B_MODIFIED: "Adaptable with local data and Malayalam language",
        AdaptabilityClassification.TIER_C_REDESIGN: "Requires fundamental redesign for tropical realities",
        AdaptabilityClassification.TIER_D_NON_TRANSFERABLE: "Incompatible due to geographic differences",
        AdaptabilityClassification.TIER_E_LOCALLY_ORIGINATED: "Native innovation born from local Kuttanad/Wayanad conditions",
    }
    assert len(tier_descriptions) == 5
    for tier, desc in tier_descriptions.items():
        adapt = GlobalToLocalAdaptation(
            transferability_tier=tier,
            kerala_applicability=desc,
        )
        assert adapt.transferability_tier == tier
        assert len(adapt.kerala_applicability) > 0
