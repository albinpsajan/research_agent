"""Unit tests for Kerala and India Official Source Registry and Adaptation Models."""

from __future__ import annotations

from src.models.research import (
    AdaptabilityClassification,
    GlobalToLocalAdaptation,
)
from src.research.sources import (
    KeralaIndiaSourceRegistry,
    OfficialSource,
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
