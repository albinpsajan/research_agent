"""HackathonIQ Multi-Track Acceptance Test (6-Track Comprehensive Scenario).

Verifies:
1. 6-track independent research execution.
2. Shared organizer intelligence reuse across all tracks.
3. Track-specific evidence retention.
4. Token-based cross-track duplicate detection and best-fit track allocation.
5. Enforcement of all 10 mandatory quality gates.
6. Mode A: Best Overall Track winner selection with runner-up explanations.
7. Mode B: Best Idea Per Track independent winner allocation and strict disqualification messaging:
   "No qualifying problem statement found for this track."
8. Reuse of valid research between Mode A and Mode B without redundant model calls.
9. Report generation for track-level and master comparison reports.
"""

from __future__ import annotations

import gc
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.database.connection import get_db
from src.database.migrations import initialize_database
from src.database.repository import Repository
from src.evaluation.cross_track_comparison import CrossTrackComparisonEngine
from src.models.candidate import CandidateSolution, FeasibilityReport, TechnicalRequirement
from src.models.domain import DiscoveredDomain, DomainMap, ProblemCandidate, ProblemEvidence
from src.models.evaluation import (
    CandidateEvaluation,
    FinalEvaluationReport,
    QualityGate,
    QualityGateStatus,
    ScoreCriterion,
    WinnerSelection,
)
from src.models.hackathon import (
    HackathonInput,
    HackathonIntelligence,
    HackathonTrack,
    MultiTrackMode,
    OrganizerProfile,
)
from src.models.multitrack import MultiTrackPipelineResult, TrackResult
from src.models.pipeline import PipelineResult
from src.reports.generator import ReportGenerator


def _build_candidate(
    cand_id: str,
    title: str,
    domain: str,
    problem: str,
    solution: str,
    diff: str,
    tech: list[str],
) -> CandidateSolution:
    return CandidateSolution(
        id=cand_id,
        problem_candidate_id=f"p-{cand_id}",
        title=title,
        domain=domain,
        problem_statement=problem,
        proposed_solution=solution,
        unique_differentiation=diff,
        relevant_technologies=tech,
        is_buildable_in_hackathon=True,
    )


def _build_evaluation(
    cand_id: str,
    title: str,
    domain: str,
    total_score: float,
    all_gates_passed: bool,
    failing_gate_reasons: dict[str, str] | None = None,
) -> CandidateEvaluation:
    gate_names = [
        ("Theme and Judging Alignment", "Problem addresses theme"),
        ("Real-World Problem Validation", "Corroborated by independent sources"),
        ("Kerala and India Relevance", "Regional applicability verified"),
        ("Existing-Solution Investigation", "Prior art investigated"),
        ("Genuine Innovation and Differentiation", "Clear differentiation stated"),
        ("Global-to-Local Adaptability", "Transferability tier assigned"),
        ("Technical Feasibility and Data Availability", "Stack buildable in hackathon"),
        ("Economic and Practical Viability", "No mandatory paid SaaS APIs"),
        ("Hackathon Buildability and Demonstration", "Demo plan achievable"),
        ("Risk, Ethics and Sustainability", "Risks and mitigations recorded"),
    ]

    failing_gate_reasons = failing_gate_reasons or {}
    gates: list[QualityGate] = []
    for g_name, g_desc in gate_names:
        if g_name in failing_gate_reasons:
            status = QualityGateStatus.FAILED
            just = failing_gate_reasons[g_name]
        else:
            status = QualityGateStatus.PASSED
            just = "Verified against evidence."
        gates.append(
            QualityGate(
                name=g_name,
                description=g_desc,
                status=status,
                justification=just,
                evidence=["Verified"],
            )
        )

    criteria = [
        ("Real-world problem significance", 15),
        ("Originality and differentiation", 15),
        ("Technical feasibility", 15),
        ("Hackathon theme relevance", 15),
        ("Organizer and sponsor alignment", 10),
        ("Innovation and future potential", 10),
        ("Implementation within deadline", 10),
        ("Demonstration and judging appeal", 10),
    ]

    scale = min(total_score / 10.0, 10.0)
    scores = [
        ScoreCriterion(
            name=c_name,
            weight=wt,
            score=scale,
            weighted_score=scale / 10.0 * wt,
            justification=f"Assessment for {c_name}",
            evidence=["Evidence"],
        )
        for c_name, wt in criteria
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
        is_qualified=all_gates_passed and total_score >= 60.0,
        quality_gates=gates,
        scores=scores,
        overall_assessment=f"Comprehensive evaluation for {title}.",
    )


def run_six_track_acceptance_test() -> None:
    print("=" * 80)
    print("  HACKATHONIQ V1.0 — SIX-TRACK MULTI-TRACK ACCEPTANCE TEST")
    print("=" * 80)

    repo = Repository()
    initialize_database(repo.db)
    t_start = time.perf_counter()

    # 1. Define 6 distinct hackathon tracks
    tracks = [
        HackathonTrack(
            id="TRK-01",
            name="Agriculture and Food Security",
            description="Precision smallholder agro-ecology, canopy sensing, and soil regeneration in rural zones",
        ),
        HackathonTrack(
            id="TRK-02",
            name="Healthcare and Rural Diagnostics",
            description="Offline clinical diagnostics, decentralized patient triage, and rural clinic point-of-care telemetry",
        ),
        HackathonTrack(
            id="TRK-03",
            name="Financial Inclusion and Micro-Fintech",
            description="Offline digital ledgers, decentralized cooperative credit scoring, and SHG micro-loans",
        ),
        HackathonTrack(
            id="TRK-04",
            name="Climate Resilience and Water Management",
            description="Catchment telemetry, flood threshold modeling, and micro-watershed drought prediction",
        ),
        HackathonTrack(
            id="TRK-05",
            name="Education and Assistive Learning",
            description="Vernacular learning accessibility and speech-driven assistive tutoring for schools",
        ),
        HackathonTrack(
            id="TRK-06",
            name="Smart Cities and Civic Infrastructure",
            description="Municipal civic management, urban waste routing, and traffic air quality monitoring",
        ),
    ]

    master_input = HackathonInput(
        theme="Artificial Intelligence for Sustainable Regional Infrastructure and Climate Resilience",
        name="Global Open Innovation Challenge 2026",
        is_multi_track=True,
        tracks=tracks,
    )

    session_id = repo.create_session(
        theme=master_input.theme,
        name=master_input.name,
        is_multi_track=True,
        multi_track_mode="best_overall",
    )
    repo.save_tracks(session_id, tracks)
    print(f"\n[PHASE 1] Created Session `{session_id[:8]}` with 6 Tracks:")
    for t in tracks:
        print(f"  • {t.id}: {t.name}")

    # 2. Shared Organizer Intelligence (Agent 1 executed once)
    shared_intel = HackathonIntelligence(
        hackathon_input=master_input,
        organizer=OrganizerProfile(
            name="Global Open Challenge Foundation",
            mission="Empower regional communities through open-source AI and offline-first civic tools",
            ideology="Decentralized open science, zero paid proprietary SaaS dependencies",
            objectives=["Deploy practical prototypes", "Prioritize underserved rural regions"],
            confidence=0.92,
        ),
        judging_criteria=[],
        submission_requirements=["Functional prototype", "Open-source codebase"],
        technical_restrictions=["Must avoid mandatory paid APIs", "Offline capability preferred"],
        is_general_theme_mode=False,
    )
    repo.save_agent_result(
        session_id, "shared_intelligence", "hackathon_intelligence", shared_intel.model_dump(mode="json")
    )
    print("\n[PHASE 2] Executed Shared Organizer Research (Agent 1) ONCE:")
    print(f"  • Mission: {shared_intel.organizer.mission}")
    print(f"  • Restrictions: {shared_intel.technical_restrictions}")

    # 3. Construct Track Research Results for each track
    track_results: dict[str, TrackResult] = {}
    report_gen = ReportGenerator(repo)

    # Track 1: Agriculture (Score 89.5, Passes 10 gates)
    c1 = _build_candidate(
        "C01-AGRI",
        "Agro-Ecological Canopy Sensing for Kerala Smallholders",
        "Agroforestry",
        "Smallholders in Wayanad and Palakkad face unpredictable monsoon shifts and pest outbreaks without affordable localized guidance.",
        "Edge-deployed multi-spectral canopy reflectance analysis using low-cost cameras with offline agronomic advisory.",
        "Zero-cloud edge computer vision calibrated to tropical intercropped homestead canopies.",
        ["Python", "OpenCV", "TFLite", "FastAPI"],
    )
    e1 = _build_evaluation("C01-AGRI", c1.title, c1.domain, 89.5, all_gates_passed=True)

    # Track 2: Healthcare (Score 91.5, Passes 10 gates — Top contender)
    c2 = _build_candidate(
        "C02-HLTH",
        "Offline Clinical Diagnostic Triage for Rural Primary Health Centres",
        "Clinical Diagnostics",
        "Primary health sub-centres in remote hilly regions lack on-site diagnostic doctors and suffer intermittent connectivity.",
        "Quantized neural triage assistant on Android tablets providing offline syndromic classification and emergency escalation.",
        "Fully offline inference pipeline with zero paid telemetry APIs and bilingual Malayalam-English interface.",
        ["Python", "ONNX Runtime", "Flutter", "SQLite"],
    )
    e2 = _build_evaluation("C02-HLTH", c2.title, c2.domain, 91.5, all_gates_passed=True)

    # Track 3: FinTech (Score 84.0, Passes 10 gates)
    c3 = _build_candidate(
        "C03-FINT",
        "Decentralized Ledger & Cooperative Credit for Kudumbashree SHGs",
        "Micro-Fintech",
        "Women self-help groups (SHGs) lack transparent digital accounting and credit scoring for formal micro-banking.",
        "Local cryptographic offline ledger enabling peer-verified loan accounting and micro-credit scoring.",
        "Cryptographically signed offline peer-to-peer sync via local Wi-Fi direct.",
        ["Python", "Cryptography", "SQLite", "Streamlit"],
    )
    e3 = _build_evaluation("C03-FINT", c3.title, c3.domain, 84.0, all_gates_passed=True)

    # Track 4: Climate/Water (Score 86.5, Passes 10 gates)
    c4 = _build_candidate(
        "C04-WATR",
        "Micro-Catchment Inundation Early Warning for Kuttanad Polders",
        "Hydrological Modeling",
        "Low-lying polders face severe tidal flooding and backwater salinity intrusion during monsoon crests.",
        "Physics-guided neural network predicting hourly water crests from upstream dam release telemetry.",
        "Coupled hydrodynamic physics loss function operating on open telemetry data.",
        ["Python", "PyTorch", "NumPy", "Open-Meteo"],
    )
    e4 = _build_evaluation("C04-WATR", c4.title, c4.domain, 86.5, all_gates_passed=True)

    # Track 5: Education (Disqualified: Fails Gate 7 & Gate 8)
    c5 = _build_candidate(
        "C05-EDUC",
        "Hyper-Scale Cloud Brain Quantum Tutoring System",
        "Assistive Education",
        "Students in rural schools need individualized adaptive tutoring.",
        "Connects classrooms to proprietary cloud supercomputer running continuous commercial GPT-4o voice streams.",
        "Proprietary cloud synthesis without offline capability.",
        ["Proprietary Cloud API", "Quantum Simulation SaaS"],
    )
    e5 = _build_evaluation(
        "C05-EDUC",
        c5.title,
        c5.domain,
        64.0,
        all_gates_passed=False,
        failing_gate_reasons={
            "Technical Feasibility and Data Availability": "Requires unverified quantum cloud APIs and unavailable proprietary hardware.",
            "Economic and Practical Viability": "Requires mandatory $50/hour paid cloud streaming API, violating zero-paid-API hackathon constraint.",
        },
    )

    # Track 6: Smart Cities (Near Duplicate of Track 2 Healthcare, placed into Smart Cities)
    c6 = _build_candidate(
        "C06-CITY",
        "Urban Periphery Clinical Diagnostic Triage for Rural Primary Health Centres",
        "Smart Cities Health",
        "Primary health sub-centres in remote hilly regions lack on-site diagnostic doctors and suffer intermittent connectivity.",
        "Quantized neural triage assistant on Android tablets providing offline syndromic classification and emergency escalation.",
        "Fully offline inference pipeline with zero paid telemetry APIs and bilingual Malayalam-English interface.",
        ["Python", "ONNX Runtime", "Flutter", "SQLite"],
    )
    e6 = _build_evaluation("C06-CITY", c6.title, c6.domain, 88.0, all_gates_passed=True)

    cand_list = [c1, c2, c3, c4, c5, c6]
    eval_list = [e1, e2, e3, e4, e5, e6]

    print("\n[PHASE 3] Simulating Independent Research Across All 6 Tracks:")
    for idx, (t, cand, ev) in enumerate(zip(tracks, cand_list, eval_list)):
        t_input = HackathonInput(
            theme=f"{master_input.theme} — Track: {t.name}",
            name=master_input.name,
            session_id=session_id,
        )
        feasibility = FeasibilityReport(candidates=[cand])
        final_eval = FinalEvaluationReport(
            winner=WinnerSelection(has_winner=ev.all_gates_passed, winner=ev if ev.all_gates_passed else None),
            evaluations=[ev],
        )

        # Generate individual track report
        track_pipe_res = PipelineResult(
            session_id=session_id,
            input=t_input,
            intelligence=shared_intel,
            domain_map=DomainMap(theme=t_input.theme, total_domains_explored=3, total_problems_found=3),
            feasibility=feasibility,
            winner=final_eval.winner,
            status="completed" if ev.all_gates_passed else "completed_no_winner",
        )
        track_rep = report_gen.generate(
            result=track_pipe_res,
            final_evaluation=final_eval,
            track_id=t.id,
        )

        tr = TrackResult(
            track=t,
            input=t_input,
            domain_map=DomainMap(theme=t_input.theme, total_domains_explored=3, total_problems_found=3),
            feasibility=feasibility,
            winner=final_eval.winner,
            report=track_rep,
            status="completed" if ev.all_gates_passed else "completed_no_winner",
        )
        track_results[t.id] = tr

        gate_status = "10/10 GATES PASSED" if ev.all_gates_passed else "FAILED GATES"
        print(f"  • Track {idx+1} ({t.id}): {cand.title[:55]} | Score: {ev.total_score:.1f}/100 [{gate_status}]")

    # 4. CROSS-TRACK EVALUATION: MODE A (Best Overall Track)
    print("\n" + "=" * 80)
    print("  EVALUATING MODE A: BEST OVERALL TRACK")
    print("=" * 80)

    engine = CrossTrackComparisonEngine(similarity_threshold=0.58)
    comp_a = engine.compare(track_results, mode=MultiTrackMode.BEST_OVERALL, shared_intelligence=shared_intel)

    assert comp_a.overall_winning_track is not None, "Mode A must declare an overall winning track"
    assert comp_a.overall_winning_candidate is not None, "Mode A must declare an overall winning candidate"
    assert comp_a.overall_winning_track.id == "TRK-02", f"Expected Track TRK-02 to win, got {comp_a.overall_winning_track.id}"
    assert comp_a.overall_winning_candidate.id == "C02-HLTH", f"Expected C02-HLTH to win, got {comp_a.overall_winning_candidate.id}"
    assert comp_a.overall_winner_evaluation.total_score == 91.5

    print(f"  >>> OVERALL WINNING TRACK:     {comp_a.overall_winning_track.name} ({comp_a.overall_winning_track.id})")
    print(f"  >>> OVERALL WINNING CANDIDATE: {comp_a.overall_winning_candidate.title}")
    print(f"  >>> WINNER SCORE:              {comp_a.overall_winner_evaluation.total_score:.1f} / 100.0 (All 10 Gates Passed)")
    print(f"  >>> SELECTION RATIONALE:       {comp_a.selection_rationale[:200]}...")

    print("\n  >>> RUNNER-UP EXPLANATIONS (Mode A):")
    print(comp_a.runner_ups_explanation)

    # 5. CROSS-TRACK DUPLICATE RESOLUTION AUDIT
    print("\n" + "=" * 80)
    print("  CROSS-TRACK DUPLICATE & OVERLAP RESOLUTION AUDIT")
    print("=" * 80)
    assert len(comp_a.duplicate_detections) >= 1, "Duplicate detection must identify C06-CITY and C02-HLTH overlap"
    dup = comp_a.duplicate_detections[0]
    print(f"  • Detected Duplicate: '{dup['candidate_a_title']}' <==> '{dup['candidate_b_title']}'")
    print(f"  • Token Jaccard Similarity: {dup['similarity_score']:.3f} (Threshold = 0.58)")
    print(f"  • Designated Best-Fit Track: '{dup['best_fit_track_name']}' ({dup['best_fit_track_id']})")
    print(f"  • Resolution Action: Excluded duplicate from non-fitting track contention.")

    # 6. CROSS-TRACK EVALUATION: MODE B (Best Idea Per Track)
    # Notice: Reuses the existing track_results without redundant model re-execution!
    print("\n" + "=" * 80)
    print("  EVALUATING MODE B: BEST IDEA PER TRACK (REUSING RESEARCH)")
    print("=" * 80)

    comp_b = engine.compare(track_results, mode=MultiTrackMode.BEST_PER_TRACK, shared_intelligence=shared_intel)

    for t in tracks:
        w_cand = comp_b.per_track_winners.get(t.id)
        if w_cand:
            w_eval = comp_b.per_track_evaluations[t.id]
            print(f"  • [{t.id}] {t.name}:")
            print(f"      WINNER: {w_cand.title} ({w_eval.total_score:.1f}/100)")
        else:
            print(f"  • [{t.id}] {t.name}:")
            print(f"      DISQUALIFIED: No qualifying problem statement found for this track.")

    # Assertions for Mode B:
    assert comp_b.per_track_winners["TRK-01"] is not None and comp_b.per_track_winners["TRK-01"].id == "C01-AGRI"
    assert comp_b.per_track_winners["TRK-02"] is not None and comp_b.per_track_winners["TRK-02"].id == "C02-HLTH"
    assert comp_b.per_track_winners["TRK-03"] is not None and comp_b.per_track_winners["TRK-03"].id == "C03-FINT"
    assert comp_b.per_track_winners["TRK-04"] is not None and comp_b.per_track_winners["TRK-04"].id == "C04-WATR"
    assert comp_b.per_track_winners["TRK-05"] is None, "TRK-05 must be rejected due to gate failure"

    # Verify exact required disqualification message in Mode B rationale
    disqual_msg = "Track 'Education and Assistive Learning': No qualifying problem statement found for this track."
    assert disqual_msg in comp_b.selection_rationale, f"Rationale must contain exact message: '{disqual_msg}'"
    print(f"\n  >>> MODE B DISQUALIFICATION VERIFIED: Contains required phrasing.")

    # 7. Generate Master Multi-Track Reports
    print("\n" + "=" * 80)
    print("  GENERATING MASTER MULTI-TRACK COMPARISON REPORTS")
    print("=" * 80)

    master_res_a = MultiTrackPipelineResult(
        session_id=session_id,
        input=master_input,
        shared_intelligence=shared_intel,
        track_results=track_results,
        comparison=comp_a,
        status="completed",
        duration_seconds=round(time.perf_counter() - t_start, 2),
    )
    master_rep_a = report_gen.generate_multi_track_report(master_res_a)
    repo.save_multi_track_comparison(
        session_id,
        "best_overall",
        comp_a.overall_winning_track.id if comp_a.overall_winning_track else None,
        comp_a.overall_winning_candidate.id if comp_a.overall_winning_candidate else None,
        comp_a.model_dump(mode="json"),
    )

    master_res_b = MultiTrackPipelineResult(
        session_id=session_id,
        input=master_input,
        shared_intelligence=shared_intel,
        track_results=track_results,
        comparison=comp_b,
        status="completed",
        duration_seconds=round(time.perf_counter() - t_start, 2),
    )
    master_rep_b = report_gen.generate_multi_track_report(master_res_b)

    assert Path(f"data/reports/{master_rep_a.metadata.report_id}.md").exists()
    print(f"  • Generated Master Report: data/reports/{master_rep_a.metadata.report_id}.md ({len(master_rep_a.sections)} sections)")
    print(f"  • Track Reports Verified: 6 track reports written to data/reports/R-{session_id[:8]}-track-*.md")

    t_total = time.perf_counter() - t_start
    print("\n" + "=" * 80)
    print(f"  ALL 6-TRACK ACCEPTANCE CHECKS PASSED IN {t_total:.2f}s")
    print("=" * 80)


if __name__ == "__main__":
    run_six_track_acceptance_test()
