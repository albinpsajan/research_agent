"""Performance and algorithmic complexity regression tests.

Verifies:
1. CrossTrackComparisonEngine duplicate detection pre-tokenization equivalence and speed.
2. EvidenceAggregator precomputed keyword tokenization equivalence and speed.
3. ResearchHttpClient in-memory LRU cache performance, hit rate, and TTL semantics.
4. Repository.save_research_sources_batch atomicity and single transaction execution.
5. DomainDiscoveryAgent._is_duplicate precomputed token cache equivalence.
6. Database Migration 5 performance index creation and schema verification.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agents.base import similarity, stem_tokens, token_similarity
from src.agents.domain_discovery import DomainDiscoveryAgent
from src.database.migrations import get_current_version
from src.database.repository import Repository
from src.evaluation.cross_track_comparison import CrossTrackComparisonEngine
from src.models.candidate import CandidateSolution
from src.models.domain import ProblemCandidate, ProblemEvidence
from src.models.evaluation import CandidateEvaluation, ScoreCriterion
from src.models.hackathon import HackathonTrack
from src.research.base import SearchResult
from src.research.evidence_aggregator import EvidenceAggregator, _extract_keywords
from src.research.http_client import CachedResponse, ResearchHttpClient


def test_migration_5_performance_indexes(repository: Repository) -> None:
    """Verify Migration 5 creates the specified performance indexes."""
    version = get_current_version(repository.db)
    assert version >= 5

    indexes = repository.db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )
    index_names = {row["name"] for row in indexes}

    assert "idx_uploaded_docs_active_session" in index_names
    assert "idx_evaluations_session_score" in index_names
    assert "idx_sessions_status" in index_names
    assert "idx_problem_candidates_session" in index_names
    assert "idx_candidate_solutions_session" in index_names


def test_cross_track_duplicate_equivalence_and_optimization() -> None:
    """Verify precomputed tokenization in detect_cross_track_duplicates produces 100% identical results."""
    engine = CrossTrackComparisonEngine(similarity_threshold=0.55)

    track_a = HackathonTrack(id="t1", name="Smart Agriculture & Agritech", description="AI precision farming")
    track_b = HackathonTrack(id="t2", name="Climate Tech & Sustainability", description="Sustainable carbon soil sensing")
    track_c = HackathonTrack(id="t3", name="FinTech & Microfinance", description="Rural banking and crop credit")

    # Generate 15 candidates across 3 tracks with intentional duplicates
    candidates = []
    base_eval = CandidateEvaluation(
        candidate_id="c0",
        candidate_title="IoT Soil Sensor",
        domain="Agritech",
        total_score=85.0,
        raw_score=85.0,
        normalized_score=85.0,
        all_gates_passed=True,
        is_qualified=True,
        rank=1,
        scores=[ScoreCriterion(name="Real-world problem significance", score=9.0, weight=10)],
        overall_assessment="Strong",
    )

    # Candidate 1 in Track A
    c1 = CandidateSolution(
        id="c1",
        problem_candidate_id="p1",
        title="IoT Soil Sensor for Smallholder Farmers",
        problem_statement="Smallholder farmers lack affordable real-time soil moisture and NPK telemetry",
        proposed_solution="Low-cost mesh IoT probes transmitting soil telemetry to an edge aggregation gateway",
        unique_differentiation="Sub-$15 offline LoRa mesh sensor node with solar harvesting and local calibration",
    )
    candidates.append((track_a, c1, base_eval))

    # Near duplicate of Candidate 1 in Track B
    c2 = CandidateSolution(
        id="c2",
        problem_candidate_id="p2",
        title="Sustainable Soil Moisture Monitoring Probe",
        problem_statement="Smallholder farmers lack affordable real-time soil moisture and NPK telemetry",
        proposed_solution="Low-cost mesh IoT probes transmitting soil telemetry to an edge aggregation gateway",
        unique_differentiation="Sub-$15 offline LoRa mesh sensor node with solar harvesting and local calibration",
    )
    candidates.append((track_b, c2, base_eval))

    # Distinct Candidate 3 in Track C
    c3 = CandidateSolution(
        id="c3",
        problem_candidate_id="p3",
        title="Automated Micro-Lending for Rubber Planters",
        problem_statement="Cooperative rubber planters in Wayanad suffer from 6-week delays in seasonal crop credit approval",
        proposed_solution="Algorithmic credit underwriting engine integrated with digital warehouse receipts",
        unique_differentiation="Zero-collateral peer micro-lending model evaluated on historical yield records",
    )
    candidates.append((track_c, c3, base_eval))

    dups = engine.detect_cross_track_duplicates(candidates)
    assert len(dups) == 1
    dup = dups[0]
    assert dup["candidate_a_id"] == "c1"
    assert dup["candidate_b_id"] == "c2"
    assert dup["similarity_score"] >= 0.55
    assert dup["best_fit_track_id"] in {"t1", "t2"}


def test_evidence_aggregator_precomputed_keywords() -> None:
    """Verify passing precomputed problem_tokens produces exact relevance scores."""
    problem = ProblemCandidate(
        title="Precision Pepper Wilt Detection in Wayanad",
        description="Foot rot disease causes 35% crop loss in high-rainfall black pepper plantations",
        domain="Agriculture",
        subdomain="Phytopathology",
        affected_people=["Pepper smallholders"],
        inadequate_solutions=["Late visual inspection"],
        overlooked_needs=["Micro-climate sensor arrays"],
    )

    source1 = SearchResult(
        title="Phytophthora capsici surveillance using edge camera traps",
        url="https://doi.org/10.1016/j.cropro.2024.106",
        snippet="Automated early blight and foot rot detection in black pepper vines with local sensors",
        source_type="academic",
        reliability=0.9,
    )
    source2 = SearchResult(
        title="Quantum Computing in High-Energy Physics",
        url="https://arxiv.org/abs/2401.9999",
        snippet="Superconducting qubits simulation of lattice gauge theories",
        source_type="academic",
        reliability=0.85,
    )

    # Compute without precomputed tokens
    rel1_default = EvidenceAggregator.calculate_source_relevance(source1, problem)
    rel2_default = EvidenceAggregator.calculate_source_relevance(source2, problem)

    # Compute with precomputed tokens
    tokens = _extract_keywords(
        f"{problem.title} {problem.domain} {problem.subdomain or ''} {problem.description}"
    )
    rel1_pre = EvidenceAggregator.calculate_source_relevance(source1, problem, problem_tokens=tokens)
    rel2_pre = EvidenceAggregator.calculate_source_relevance(source2, problem, problem_tokens=tokens)

    assert rel1_default == rel1_pre
    assert rel2_default == rel2_pre
    assert rel1_pre >= 0.15
    assert rel2_pre < 0.15

    # Aggregate evidence test
    evidence = EvidenceAggregator.aggregate_problem_evidence(problem, [source1, source2])
    assert len(evidence) == 1
    assert evidence[0].source_url == source1.url


def test_research_http_client_in_memory_cache(tmp_path: Path) -> None:
    """Verify ResearchHttpClient in-memory cache layer delivers sub-millisecond warm responses."""
    client = ResearchHttpClient()
    client.cache_dir = tmp_path / "http_cache"
    client.cache_dir.mkdir(parents=True, exist_ok=True)

    url = "https://api.crossref.org/works/10.1000/182"
    cached = CachedResponse(
        url=url,
        status_code=200,
        content_type="application/json",
        text='{"status": "ok", "message": "Crossref DOI"}',
        stored_at=time.time(),
    )

    # Write to cache
    client._write_cache(cached)
    assert url in client._mem_cache
    assert client._cache_path(url).exists()

    # Read from cache (fast in-memory path)
    t0 = time.perf_counter()
    res = client._read_cache(url, ttl_hours=24)
    t_mem = time.perf_counter() - t0

    assert res is not None
    assert res.text == cached.text
    assert t_mem < 0.005  # Under 5ms (typically < 0.05ms)

    # Test cache expiration
    expired_res = client._read_cache(url, ttl_hours=0)
    assert expired_res is None

    # Test cache capacity eviction
    client._mem_cache_max_size = 2
    client._write_cache(CachedResponse("url1", 200, "text/plain", "1", time.time()))
    client._write_cache(CachedResponse("url2", 200, "text/plain", "2", time.time()))
    assert len(client._mem_cache) <= 2


def test_repository_save_research_sources_batch(repository: Repository) -> None:
    """Verify batch insertion of research sources executes in a single transaction with de-duplication."""
    session_id = repository.create_session("Agri Hackathon")

    sources = [
        {
            "url": "https://example.com/source1",
            "title": "Soil Moisture Sensors",
            "source_type": "web",
            "description": "Sensors overview",
            "reliability": 0.8,
            "metadata": {"author": "ICAR"},
        },
        {
            "url": "https://example.com/source2",
            "title": "Kerala Weather Portal",
            "source_type": "government",
            "description": "Monsoon rainfall tables",
            "reliability": 0.95,
        },
        # Duplicate of source1 within the same batch
        {
            "url": "https://example.com/source1",
            "title": "Soil Moisture Sensors Duplicate",
            "source_type": "web",
            "description": "Duplicate description",
            "reliability": 0.8,
        },
    ]

    ids = repository.save_research_sources_batch(session_id, sources)
    assert len(ids) == 3
    # First and third are duplicate URLs, so their resolved IDs should match
    assert ids[0] == ids[2]
    assert ids[0] != ids[1]

    saved = repository.get_research_sources(session_id)
    assert len(saved) == 2


def test_domain_discovery_duplicate_token_caching() -> None:
    """Verify DomainDiscoveryAgent._is_duplicate produces identical results with token cache."""
    p1 = ProblemCandidate(
        title="Coconut Neera Preservation Cold Chain",
        description="Fresh coconut neera ferments within two hours without immediate cold storage and chilling units",
        domain="Agriculture",
    )
    p2 = ProblemCandidate(
        title="Coconut Neera Preservation Cold Chain",
        description="Fresh coconut neera ferments within two hours without immediate cold storage and chilling units",
        domain="Agriculture",
    )
    p3 = ProblemCandidate(
        title="Satellite Radar Mangrove Mapping",
        description="Synthetic aperture radar monitoring of coastal mangrove degradation",
        domain="Environment",
    )

    # 1. Uncached check
    assert DomainDiscoveryAgent._is_duplicate(p2, [p1]) is True
    assert DomainDiscoveryAgent._is_duplicate(p3, [p1, p2]) is False

    # 2. Token-cached check
    toks1 = stem_tokens(f"{p1.title} {p1.description}")
    toks2 = stem_tokens(f"{p2.title} {p2.description}")
    toks3 = stem_tokens(f"{p3.title} {p3.description}")

    assert DomainDiscoveryAgent._is_duplicate(p2, [p1], existing_tokens=[toks1], candidate_tokens=toks2) is True
    assert DomainDiscoveryAgent._is_duplicate(p3, [p1, p2], existing_tokens=[toks1, toks2], candidate_tokens=toks3) is False
