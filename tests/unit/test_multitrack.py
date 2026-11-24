"""Unit tests for Multi-Track Hackathon Intelligence (17 verification scenarios)."""

from __future__ import annotations

import gc
from unittest.mock import patch

from src.agents.domain_discovery import DomainListLLM, DomainLLM
from src.evaluation.cross_track_comparison import CrossTrackComparisonEngine
from src.models.candidate import CandidateSolution, FeasibilityReport
from src.models.evaluation import (
    CandidateEvaluation,
    QualityGate,
    QualityGateStatus,
    ScoreCriterion,
    WinnerSelection,
)
from src.models.hackathon import (
    HackathonInput,
    HackathonTrack,
    MultiTrackMode,
)
from src.models.multitrack import TrackResult
from src.orchestration.loader import load_session_result
from src.orchestration.pipeline import HackathonPipeline
from tests.fakes import FakeIntelligence, FakeLLM, FakeResearch


class TrackAwareFakeLLM(FakeLLM):
    """Fake LLM that customizes domain and problem generation based on track keywords."""

    def generate_json(self, prompt, schema, system=None, temperature=None):
        name = schema.__name__
        if name == "DomainListLLM":
            self.calls.append(name)
            if "Healthcare" in prompt:
                return DomainListLLM(
                    reasoning="Track focuses on health informatics and rural diagnostics.",
                    domains=[
                        DomainLLM(
                            name="Clinical Informatics",
                            description="Diagnostic support and triage for clinical environments",
                            relevance_type="primary",
                            relevance_explanation="Directly targets healthcare delivery",
                            subdomains=["triage", "offline telemetry"],
                            connections_to_theme=["clinical resilience"],
                            interdisciplinary_links=["edge computing"],
                            search_queries=["rural clinical triage evidence"],
                            confidence=0.85,
                        )
                    ],
                )
            if "Agriculture" in prompt:
                return DomainListLLM(
                    reasoning="Track focuses on precision farming and crop resilience.",
                    domains=[
                        DomainLLM(
                            name="Agro-Ecological Sensing",
                            description="Soil and canopy monitoring for smallholder crops",
                            relevance_type="primary",
                            relevance_explanation="Directly targets agricultural resilience",
                            subdomains=["soil telemetry", "pest monitoring"],
                            connections_to_theme=["crop resilience"],
                            interdisciplinary_links=["satellite remote sensing"],
                            search_queries=["agro ecological canopy sensing evidence"],
                            confidence=0.88,
                        )
                    ],
                )
        return super().generate_json(prompt, schema, system, temperature)


class TrackFailingFakeLLM(FakeLLM):
    """Fails specifically during the execution of Track 2."""

    def __init__(self, fail_track_keyword: str = "Failing Track", **kwargs) -> None:
        super().__init__(**kwargs)
        self.fail_track_keyword = fail_track_keyword

    def generate_json(self, prompt, schema, system=None, temperature=None):
        if self.fail_track_keyword in prompt and schema.__name__ == "DomainListLLM":
            raise RuntimeError(f"Simulated LLM crash in track '{self.fail_track_keyword}'")
        return super().generate_json(prompt, schema, system, temperature)


def _make_candidate(
    cand_id: str,
    title: str,
    domain: str,
    problem: str,
    solution: str,
    unique: str = "novel edge pipeline",
) -> CandidateSolution:
    return CandidateSolution(
        id=cand_id,
        problem_candidate_id=f"p-{cand_id}",
        title=title,
        domain=domain,
        problem_statement=problem,
        proposed_solution=solution,
        unique_differentiation=unique,
        is_buildable_in_hackathon=True,
    )


def _make_evaluation(
    cand_id: str,
    title: str,
    domain: str,
    total_score: float,
    all_gates_passed: bool = True,
    gate_reason: str = "Passed all checks",
) -> CandidateEvaluation:
    gate_status = QualityGateStatus.PASSED if all_gates_passed else QualityGateStatus.FAILED
    gates = [
        QualityGate(
            name="Theme Alignment",
            description="Problem addresses theme",
            status=gate_status,
            justification=gate_reason,
            evidence=["Theme verified"],
        ),
        QualityGate(
            name="Technical Feasibility",
            description="Buildable in time",
            status=gate_status,
            justification=gate_reason,
            evidence=["Stack buildable"],
        ),
    ]
    scores = [
        ScoreCriterion(
            name="Problem Significance & Impact",
            score=min(total_score / 10.0, 10.0),
            weight=15,
            weighted_score=15 * (min(total_score / 10.0, 10.0)) / 10.0,
            evidence=["Evidence"],
            justification="Justification",
        ),
        ScoreCriterion(
            name="Technical Feasibility & Implementation",
            score=min(total_score / 10.0, 10.0),
            weight=15,
            weighted_score=15 * (min(total_score / 10.0, 10.0)) / 10.0,
            evidence=["Evidence"],
            justification="Justification",
        ),
    ]
    return CandidateEvaluation(
        candidate_id=cand_id,
        candidate_title=title,
        domain=domain,
        total_score=total_score,
        raw_score=total_score,
        base_score=total_score,
        normalized_score=total_score,
        all_gates_passed=all_gates_passed,
        is_qualified=all_gates_passed,
        quality_gates=gates,
        scores=scores,
        overall_assessment="Thorough evaluation.",
    )


# --------------------------------------------------------------------------
# 17 Test Scenarios
# --------------------------------------------------------------------------


def test_scenario_01_single_track_execution(repository) -> None:
    """Scenario 1: Single-track execution via multi-track pipeline."""
    llm = FakeLLM()
    research = FakeResearch()
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )
    track = HackathonTrack(name="Agriculture and Food Security")
    hackathon = HackathonInput(
        theme="Climate Resilience",
        name="AgriHack",
        is_multi_track=True,
        multi_track_mode=MultiTrackMode.BEST_OVERALL,
        tracks=[track],
    )
    result = pipeline.run_multi_track(hackathon)

    assert result.status == "completed"
    assert len(result.track_results) == 1
    assert track.id in result.track_results
    assert result.comparison is not None
    assert result.master_report is not None
    assert len(result.master_report.sections) >= 10


def test_scenario_02_two_track_execution(repository) -> None:
    """Scenario 2: Two-track execution evaluates both tracks sequentially and produces comparison."""
    llm = FakeLLM()
    research = FakeResearch()
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )
    t1 = HackathonTrack(name="Agriculture")
    t2 = HackathonTrack(name="Healthcare")
    hackathon = HackathonInput(
        theme="Rural Innovation",
        is_multi_track=True,
        multi_track_mode=MultiTrackMode.BEST_OVERALL,
        tracks=[t1, t2],
    )
    result = pipeline.run_multi_track(hackathon)

    assert result.status == "completed"
    assert len(result.track_results) == 2
    assert t1.id in result.track_results
    assert t2.id in result.track_results
    assert result.comparison is not None
    assert len(result.comparison.ranked_candidates) >= 2


def test_scenario_03_six_track_execution(repository) -> None:
    """Scenario 3: Six-track execution (the classic hackathon benchmark)."""
    llm = FakeLLM()
    research = FakeResearch()
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )
    track_names = [
        "Agriculture & Food Security",
        "Healthcare",
        "Financial Technology",
        "Education",
        "Climate & Sustainability",
        "Smart Cities",
    ]
    tracks = [HackathonTrack(name=tn) for tn in track_names]
    hackathon = HackathonInput(
        theme="Future Cities and Societies",
        is_multi_track=True,
        multi_track_mode=MultiTrackMode.BEST_PER_TRACK,
        tracks=tracks,
    )
    result = pipeline.run_multi_track(hackathon)

    assert result.status == "completed"
    assert len(result.track_results) == 6
    for t in tracks:
        assert t.id in result.track_results
        assert result.track_results[t.id].status == "completed"


def test_scenario_04_more_than_six_tracks_execution(repository) -> None:
    """Scenario 4: More than six tracks (e.g. 8 tracks) to prove no hardcoded track limit exists."""
    llm = FakeLLM()
    research = FakeResearch()
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )
    tracks = [HackathonTrack(name=f"Specialized Domain Track {i+1}") for i in range(8)]
    hackathon = HackathonInput(
        theme="Open Innovation Grand Challenge",
        is_multi_track=True,
        multi_track_mode=MultiTrackMode.BEST_OVERALL,
        tracks=tracks,
    )
    result = pipeline.run_multi_track(hackathon)

    assert result.status == "completed"
    assert len(result.track_results) == 8


def test_scenario_05_different_domain_discoveries_across_tracks(repository) -> None:
    """Scenario 5: Different domain discoveries across different tracks."""
    llm = TrackAwareFakeLLM()
    research = FakeResearch()
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )
    t_health = HackathonTrack(name="Healthcare Innovations")
    t_agri = HackathonTrack(name="Agriculture and Soil Health")
    hackathon = HackathonInput(
        theme="Regional Technology Initiative",
        is_multi_track=True,
        tracks=[t_health, t_agri],
    )
    result = pipeline.run_multi_track(hackathon)

    health_dm = result.track_results[t_health.id].domain_map
    agri_dm = result.track_results[t_agri.id].domain_map

    assert health_dm is not None and agri_dm is not None
    health_domains = {d.name for d in health_dm.domains}
    agri_domains = {d.name for d in agri_dm.domains}

    assert "Clinical Informatics" in health_domains
    assert "Agro-Ecological Sensing" in agri_domains
    assert health_domains != agri_domains


def test_scenario_06_shared_organizer_research_executed_once(repository) -> None:
    """Scenario 6: Shared organizer research (Agent 1) is executed only once across all tracks."""
    llm = FakeLLM()
    research = FakeResearch()
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )
    tracks = [HackathonTrack(name=f"Track {i+1}") for i in range(3)]
    hackathon = HackathonInput(
        theme="Shared Organizer Test",
        name="Global Open Challenge",
        is_multi_track=True,
        tracks=tracks,
    )
    result = pipeline.run_multi_track(hackathon)

    # ScoutLLM and HackathonIntelLLM (Agent 1) should be invoked exactly once
    scout_calls = [c for c in llm.calls if c == "ScoutLLM"]
    intel_calls = [c for c in llm.calls if c == "HackathonIntelLLM"]
    assert len(scout_calls) == 1
    assert len(intel_calls) == 1
    assert result.shared_intelligence is not None


def test_scenario_07_independent_track_research(repository) -> None:
    """Scenario 7: Independent track research (queries, evidence, feasibility, candidates independent)."""
    llm = FakeLLM()
    research = FakeResearch()
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )
    t1 = HackathonTrack(name="Track Alpha")
    t2 = HackathonTrack(name="Track Beta")
    hackathon = HackathonInput(
        theme="Independent Research Verification",
        is_multi_track=True,
        tracks=[t1, t2],
    )
    result = pipeline.run_multi_track(hackathon)

    res1 = result.track_results[t1.id]
    res2 = result.track_results[t2.id]

    assert res1.domain_map is not None and res2.domain_map is not None
    assert res1.feasibility is not None and res2.feasibility is not None
    # Track inputs should have distinct themes with track suffix
    assert "Track Alpha" in res1.input.theme
    assert "Track Beta" in res2.input.theme


def test_scenario_08_track_specific_evidence_no_leakage(repository) -> None:
    """Scenario 8: Track-specific evidence verification with independent session tracking."""
    llm = FakeLLM()
    research = FakeResearch()
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )
    t1 = HackathonTrack(name="Energy Grid")
    t2 = HackathonTrack(name="Marine Conservation")
    hackathon = HackathonInput(
        theme="Planetary Health",
        is_multi_track=True,
        tracks=[t1, t2],
    )
    result = pipeline.run_multi_track(hackathon)

    # Both tracks produced individual track reports with evidence links
    rep1 = result.track_results[t1.id].report
    rep2 = result.track_results[t2.id].report
    assert rep1 is not None and rep2 is not None
    assert rep1.metadata.report_id != rep2.metadata.report_id


def test_scenario_09_duplicate_candidate_detection_and_best_fit_resolution() -> None:
    """Scenario 9: Duplicate candidate detection and best-fit track resolution."""
    engine = CrossTrackComparisonEngine(similarity_threshold=0.55)

    track_health = HackathonTrack(id="t-health", name="Healthcare Diagnostics", description="Clinical patient triage")
    track_city = HackathonTrack(id="t-city", name="Smart Cities", description="Urban municipal infrastructure")

    cand_health = _make_candidate(
        "c-01",
        "Offline Clinical Triage System",
        "Clinical Diagnostics",
        "Rural health clinics lack automated diagnostic triage on low-cost tablets.",
        "Deploy lightweight quantized neural model on tablets for offline patient risk stratification.",
        "Zero cloud dependency patient triage",
    )
    eval_health = _make_evaluation("c-01", "Offline Clinical Triage System", "Clinical Diagnostics", 89.0)

    # Near-duplicate in smart cities track
    cand_city = _make_candidate(
        "c-02",
        "Urban Offline Clinical Triage System",
        "Smart Cities Health",
        "Rural health clinics lack automated diagnostic triage on low-cost tablets in urban peripheries.",
        "Deploy lightweight quantized neural model on tablets for offline patient risk stratification.",
        "Zero cloud dependency patient triage",
    )
    eval_city = _make_evaluation("c-02", "Urban Offline Clinical Triage System", "Smart Cities Health", 86.0)

    items = [
        (track_health, cand_health, eval_health),
        (track_city, cand_city, eval_city),
    ]

    duplicates = engine.detect_cross_track_duplicates(items)
    assert len(duplicates) == 1
    dup = duplicates[0]
    assert dup["best_fit_track_name"] == "Healthcare Diagnostics"
    assert dup["similarity_score"] >= 0.55


def test_scenario_10_best_overall_track_selection_mode_a() -> None:
    """Scenario 10: Best Overall Track selection (Mode A) with runner-up explanations."""
    engine = CrossTrackComparisonEngine()

    t_agri = HackathonTrack(id="t-agri", name="Agriculture")
    t_health = HackathonTrack(id="t-health", name="Healthcare")

    cand_agri = _make_candidate("c-agri", "AgroForestry AI", "Agroforestry", "Soil degradation", "Micro-canopy sensing")
    eval_agri = _make_evaluation("c-agri", "AgroForestry AI", "Agroforestry", 91.5)

    cand_health = _make_candidate("c-health", "Clinic AI", "Healthcare", "Patient triage", "Offline tablet model")
    eval_health = _make_evaluation("c-health", "Clinic AI", "Healthcare", 85.0)

    tr_agri = TrackResult(
        track=t_agri,
        input=HackathonInput(theme="Agri"),
        feasibility=FeasibilityReport(candidates=[cand_agri]),
        winner=WinnerSelection(has_winner=True, winner=eval_agri),
        status="completed",
    )
    tr_health = TrackResult(
        track=t_health,
        input=HackathonInput(theme="Health"),
        feasibility=FeasibilityReport(candidates=[cand_health]),
        winner=WinnerSelection(has_winner=True, winner=eval_health),
        status="completed",
    )

    res = engine.compare(
        {"t-agri": tr_agri, "t-health": tr_health},
        mode=MultiTrackMode.BEST_OVERALL,
    )

    assert res.overall_winning_track is not None
    assert res.overall_winning_track.id == "t-agri"
    assert res.overall_winning_candidate is not None
    assert res.overall_winning_candidate.id == "c-agri"
    assert len(res.runner_ups_explanation) >= 1
    assert "Healthcare" in res.runner_ups_explanation


def test_scenario_11_best_idea_per_track_selection_mode_b() -> None:
    """Scenario 11: Best Idea Per Track selection (Mode B) independently crowns qualifying winners."""
    engine = CrossTrackComparisonEngine()

    t1 = HackathonTrack(id="t-1", name="Agriculture Track")
    t2 = HackathonTrack(id="t-2", name="Healthcare Track")

    c1 = _make_candidate(
        "c-1",
        "Agro Canopy AI",
        "Agriculture",
        "Crop canopy thermal monitoring",
        "Edge thermal camera inference",
        "Thermal canopy gradient estimation",
    )
    e1 = _make_evaluation("c-1", "Agro Canopy AI", "Agriculture", 88.0)

    c2 = _make_candidate(
        "c-2",
        "Clinical Triage AI",
        "Healthcare",
        "Patient triage bottleneck",
        "Offline diagnostic tablet triage",
        "Decentralized offline EHR triage",
    )
    e2 = _make_evaluation("c-2", "Clinical Triage AI", "Healthcare", 84.0)

    tr1 = TrackResult(
        track=t1,
        input=HackathonInput(theme="Track 1 Theme"),
        feasibility=FeasibilityReport(candidates=[c1]),
        winner=WinnerSelection(has_winner=True, winner=e1),
        status="completed",
    )
    tr2 = TrackResult(
        track=t2,
        input=HackathonInput(theme="Track 2 Theme"),
        feasibility=FeasibilityReport(candidates=[c2]),
        winner=WinnerSelection(has_winner=True, winner=e2),
        status="completed",
    )

    res = engine.compare(
        {"t-1": tr1, "t-2": tr2},
        mode=MultiTrackMode.BEST_PER_TRACK,
    )

    assert "t-1" in res.per_track_winners and res.per_track_winners["t-1"] is not None
    assert res.per_track_winners["t-1"].id == "c-1"

    assert "t-2" in res.per_track_winners and res.per_track_winners["t-2"] is not None
    assert res.per_track_winners["t-2"].id == "c-2"


def test_scenario_12_track_where_no_candidate_passes() -> None:
    """Scenario 12: A track where no candidate passes mandatory gates produces exact required message."""
    engine = CrossTrackComparisonEngine()

    t_qual = HackathonTrack(id="t-qual", name="FinTech")
    t_disqual = HackathonTrack(id="t-disqual", name="Quantum")

    c_qual = _make_candidate("c-q", "Micro-Lending AI", "FinTech", "Credit scoring", "Local ledger")
    e_qual = _make_evaluation("c-q", "Micro-Lending AI", "FinTech", 87.0, all_gates_passed=True)

    c_disqual = _make_candidate("c-dq", "Quantum Cryptography", "Quantum", "Key exchange", "Simulation")
    e_disqual = _make_evaluation(
        "c-dq",
        "Quantum Cryptography",
        "Quantum",
        65.0,
        all_gates_passed=False,
        gate_reason="Failed Gate 4: Technical Feasibility in 36h hackathon",
    )

    tr_qual = TrackResult(
        track=t_qual,
        input=HackathonInput(theme="FinTech Theme"),
        feasibility=FeasibilityReport(candidates=[c_qual]),
        winner=WinnerSelection(has_winner=True, winner=e_qual),
        status="completed",
    )
    tr_disqual = TrackResult(
        track=t_disqual,
        input=HackathonInput(theme="Quantum Theme"),
        feasibility=FeasibilityReport(candidates=[c_disqual]),
        winner=WinnerSelection(has_winner=False, rejection_reason="No qualifying candidate"),
        status="completed",
    )

    res = engine.compare(
        {"t-qual": tr_qual, "t-disqual": tr_disqual},
        mode=MultiTrackMode.BEST_PER_TRACK,
    )

    assert res.per_track_winners["t-qual"] is not None
    assert res.per_track_winners["t-disqual"] is None

    # Verify disqualification explanation explicitly contains required text
    assert "No qualifying problem statement found for this track." in res.selection_rationale


def test_scenario_13_all_tracks_failing_qualification_honest_rejection() -> None:
    """Scenario 13: All tracks failing qualification results in honest rejection across all tracks."""
    engine = CrossTrackComparisonEngine()

    t1 = HackathonTrack(id="t-1", name="Track 1")
    t2 = HackathonTrack(id="t-2", name="Track 2")

    c1 = _make_candidate("c-1", "Overpromising AI", "Domain 1", "P1", "S1")
    e1 = _make_evaluation("c-1", "Overpromising AI", "Domain 1", 72.0, all_gates_passed=False)

    c2 = _make_candidate("c-2", "Vague Platform", "Domain 2", "P2", "S2")
    e2 = _make_evaluation("c-2", "Vague Platform", "Domain 2", 69.0, all_gates_passed=False)

    tr1 = TrackResult(
        track=t1,
        input=HackathonInput(theme="Track 1 Theme"),
        feasibility=FeasibilityReport(candidates=[c1]),
        winner=WinnerSelection(has_winner=False),
        status="completed",
    )
    tr2 = TrackResult(
        track=t2,
        input=HackathonInput(theme="Track 2 Theme"),
        feasibility=FeasibilityReport(candidates=[c2]),
        winner=WinnerSelection(has_winner=False),
        status="completed",
    )

    # Mode A test
    res_a = engine.compare({"t-1": tr1, "t-2": tr2}, mode=MultiTrackMode.BEST_OVERALL)
    assert res_a.overall_winning_track is None
    assert res_a.overall_winning_candidate is None

    # Mode B test
    res_b = engine.compare({"t-1": tr1, "t-2": tr2}, mode=MultiTrackMode.BEST_PER_TRACK)
    assert res_b.per_track_winners["t-1"] is None
    assert res_b.per_track_winners["t-2"] is None


def test_scenario_14_track_specific_official_judging_criteria_mapping(repository) -> None:
    """Scenario 14: Track-specific official judging criteria, rules, and URL mapping."""
    llm = FakeLLM()
    research = FakeResearch()
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )
    track = HackathonTrack(
        name="Embedded Edge AI",
        description="Edge IoT systems running with <2W power",
        track_rules="Must run on offline microcontroller",
        official_track_url="https://example.com/tracks/embedded",
    )
    hackathon = HackathonInput(
        theme="Hardware & Software Convergence",
        is_multi_track=True,
        tracks=[track],
    )
    result = pipeline.run_multi_track(hackathon)

    track_res = result.track_results[track.id]
    assert track_res.input.website_url == "https://example.com/tracks/embedded"
    assert "Must run on offline microcontroller" in (track_res.input.constraints or "")


def test_scenario_15_resource_safe_sequential_execution_and_gc(repository) -> None:
    """Scenario 15: Resource-safe sequential execution and garbage collection between tracks."""
    llm = FakeLLM()
    research = FakeResearch()
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )
    tracks = [HackathonTrack(name=f"Track {i}") for i in range(3)]
    hackathon = HackathonInput(
        theme="Resource Monitoring Test",
        is_multi_track=True,
        tracks=tracks,
    )

    with patch("src.orchestration.pipeline.gc.collect", wraps=gc.collect) as mock_gc:
        result = pipeline.run_multi_track(hackathon)
        assert result.status == "completed"
        # gc.collect should be called after each track execution (at least 3 times)
        assert mock_gc.call_count >= 3


def test_scenario_16_fault_tolerant_recovery_when_track_fails(repository) -> None:
    """Scenario 16: Fault-tolerant recovery when one track raises an error."""
    llm = TrackFailingFakeLLM(fail_track_keyword="Crashing Track")
    research = FakeResearch()
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )
    t1 = HackathonTrack(name="Healthy Track 1")
    t2 = HackathonTrack(name="Crashing Track")
    t3 = HackathonTrack(name="Healthy Track 2")

    hackathon = HackathonInput(
        theme="Fault Tolerance Verification",
        is_multi_track=True,
        tracks=[t1, t2, t3],
    )
    result = pipeline.run_multi_track(hackathon)

    # Track 1 and 3 should complete; track 2 should be marked failed
    assert result.track_results[t1.id].status == "completed"
    assert result.track_results[t2.id].status == "failed"
    assert "Simulated LLM crash" in str(result.track_results[t2.id].error)
    assert result.track_results[t3.id].status == "completed"

    # Overall multi-track pipeline still succeeds and generates comparison
    assert result.status == "completed"
    assert result.comparison is not None
    assert result.comparison.tracks_failed == 1
    assert result.comparison.tracks_completed == 2


def test_scenario_17_historical_single_track_backward_compatibility(repository) -> None:
    """Scenario 17: Historical single-track runs operate identically and remain backward-compatible."""
    llm = FakeLLM()
    research = FakeResearch()
    pipeline = HackathonPipeline(
        llm=llm,
        repository=repository,
        research=research,
        intelligence=FakeIntelligence(),
    )
    hackathon = HackathonInput(
        theme="Single-Track Classical Theme",
        name="SoloHack",
        is_multi_track=False,
    )
    result = pipeline.run(hackathon)

    assert result.status == "completed"
    assert result.winner is not None and result.winner.has_winner
    assert result.winner.winner.candidate_title is not None

    # Verify repository functions for single-track
    session = repository.get_session(result.session_id)
    assert session is not None
    assert session["is_multi_track"] == 0

    tracks = repository.get_tracks(result.session_id)
    assert tracks == []

    # Verify load_session_result loads single track cleanly
    loaded = load_session_result(result.session_id, repository)
    assert loaded is not None
    assert loaded.session_id == result.session_id
    assert loaded.winner is not None and loaded.winner.has_winner
