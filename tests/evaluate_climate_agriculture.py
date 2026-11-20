"""HackathonIQ Phase 2: Real-World Intelligence and Quality Validation.

Evaluates:
- Theme: "Artificial Intelligence for Climate-Resilient Agriculture and Rural Communities."
- General theme research without fabricated organizer data.
- Full 5-agent LangGraph workflow with multiple finalists and multi-round debate.
- Research quality, source relevance, citations, innovation gaps.
- Adversarial competition, 7 deterministic quality gates, and winner selection.
- Hardware and local model performance (Qwen 2.5 3B).
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Ensure workspace root is in sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx

from src.database.repository import Repository
from src.llm.client import OllamaClient
from src.models.hackathon import HackathonInput
from src.models.pipeline import PipelineOptions
from src.orchestration.pipeline import HackathonPipeline
from src.research.registry import ResearchService


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def get_system_ram_mb() -> tuple[float, float, int]:
    """Return (used_mb, total_mb, percent_load) for system RAM."""
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    used_mb = (stat.ullTotalPhys - stat.ullAvailPhys) / (1024 * 1024)
    total_mb = stat.ullTotalPhys / (1024 * 1024)
    return round(used_mb, 1), round(total_mb, 1), int(stat.dwMemoryLoad)


def get_gpu_vram_mb() -> tuple[int, int]:
    """Return (used_mb, total_mb) via nvidia-smi."""
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        ).strip()
        used, total = out.split(",")
        return int(used.strip()), int(total.strip())
    except (subprocess.SubprocessError, OSError, ValueError):
        return 0, 0


def get_ollama_ps() -> dict[str, Any]:
    """Return active model details from Ollama /api/ps."""
    try:
        resp = httpx.get("http://localhost:11434/api/ps", timeout=5.0)
        return resp.json()
    except (httpx.HTTPError, OSError) as exc:
        return {"error": str(exc)}


def main() -> None:
    print("=" * 76)
    print("  HACKATHONIQ PHASE 2: REAL-WORLD INTELLIGENCE & QUALITY VALIDATION")
    print("  Theme: 'Artificial Intelligence for Climate-Resilient Agriculture")
    print("          and Rural Communities'")
    print("=" * 76)

    # ------------------------------------------------------------------
    # Step 1: Baseline Hardware & Model Verification
    # ------------------------------------------------------------------
    print("\n[PHASE 2 - STEP 1] Hardware & Local Model Verification...")
    ram_init_used, ram_init_total, ram_init_pct = get_system_ram_mb()
    gpu_init_used, gpu_init_total = get_gpu_vram_mb()
    print(
        f"  System RAM Baseline: {ram_init_used} MB used / {ram_init_total} MB total ({ram_init_pct}% load)"
    )
    print(
        f"  GPU VRAM Baseline:   {gpu_init_used} MiB used / {gpu_init_total} MiB total"
    )

    ps_info = get_ollama_ps()
    models = ps_info.get("models", [])
    if models:
        m = models[0]
        vram_bytes = m.get("size_vram", 0)
        total_bytes = m.get("size", 1)
        offload_pct = round((vram_bytes / total_bytes) * 100, 1) if total_bytes else 0
        print(
            f"  Ollama Active Model: {m.get('name')} ({m.get('details', {}).get('parameter_size')})"
        )
        print(
            f"  Runner / Context:    {m.get('runner')} | Context Window: {m.get('context_length')}"
        )
        print(
            f"  GPU Offloading:      {offload_pct}% in VRAM ({vram_bytes / (1024**2):.1f} MB)"
        )
    else:
        print("  Ollama Active Model: None currently warm in memory")

    client = OllamaClient()
    health = client.health()
    print(
        f"  Ollama Health:       available={health.get('available')}, models={health.get('models')}"
    )
    assert health.get("available"), f"Ollama not available: {health.get('error')}"
    assert "qwen2.5:3b" in str(health.get("models")), (
        "qwen2.5:3b not installed in Ollama"
    )

    # ------------------------------------------------------------------
    # Step 2: Define Realistic Hackathon Scenario (No Fake Organizer)
    # ------------------------------------------------------------------
    print("\n[PHASE 2 - STEP 2] Configuring Real-World Hackathon Scenario...")
    scenario = HackathonInput(
        theme="Artificial Intelligence for Climate-Resilient Agriculture and Rural Communities.",
        name=None,  # General theme research without fabricated organizer
        website_url=None,
        rules_url=None,
        constraints=(
            "Must address real-world smallholder farming vulnerabilities. "
            "Must function in rural low-bandwidth or offline environments. "
            "Must rely on open-source frameworks, open satellite/sensor data. "
            "Zero proprietary or paid API dependencies."
        ),
    )
    print(f"  Theme:       {scenario.theme}")
    print("  Organizer:   (None specified — general theme research mode)")
    print(f"  Constraints: {scenario.constraints}")

    pipeline_options = PipelineOptions(
        max_domains=3,
        problems_per_domain=2,
        max_finalists=3,  # 3 finalists to test multi-candidate competition
        max_debate_rounds=2,  # 2 rounds of adversarial debate
        include_continuous_intelligence=True,
    )
    print(
        f"  Options:     max_domains={pipeline_options.max_domains}, "
        f"problems_per_domain={pipeline_options.problems_per_domain}, "
        f"max_finalists={pipeline_options.max_finalists}, "
        f"max_debate_rounds={pipeline_options.max_debate_rounds}"
    )

    # ------------------------------------------------------------------
    # Step 3: Run Full 5-Agent LangGraph Workflow
    # ------------------------------------------------------------------
    print("\n[PHASE 2 - STEP 3] Executing Complete LangGraph Pipeline...")
    repo = Repository()
    research_svc = ResearchService(repo)

    stage_timings: list[dict[str, Any]] = []
    t_start = time.perf_counter()

    def progress_callback(stage: str, msg: str, pct: float) -> None:
        elapsed = time.perf_counter() - t_start
        stage_timings.append(
            {"stage": stage, "message": msg, "pct": pct, "elapsed_s": round(elapsed, 2)}
        )
        print(f"  [{elapsed:6.1f}s | {int(pct * 100):3d}%] [{stage:22s}] {msg}")

    pipeline = HackathonPipeline(
        llm=client,
        repository=repo,
        research=research_svc,
        progress=progress_callback,
    )

    result = pipeline.run(scenario, pipeline_options)
    t_total = time.perf_counter() - t_start
    print(
        f"\n  Pipeline Complete in {t_total:.2f}s ({t_total / 60:.2f} min) with status: '{result.status}'"
    )

    session_id = result.session_id
    print(f"  Session ID: {session_id}")

    # ------------------------------------------------------------------
    # Step 4: Research Quality & Source Relevance Audit
    # ------------------------------------------------------------------
    print("\n[PHASE 2 - STEP 4] Research Quality & Evidence Audit...")
    agent_results = repo.get_agent_results(session_id)
    print(
        f"  Agent Results Saved in SQLite: {[a.get('agent_name') for a in agent_results]}"
    )

    # 4.1 Domains Discovered
    domain_map = result.domain_map
    if domain_map:
        print(f"\n  4.1 Dynamically Discovered Domains ({len(domain_map.domains)}):")
        for idx, d in enumerate(domain_map.domains, 1):
            print(f"    {idx}. {d.name} ({d.relevance_type.value})")
            print(f"       Explanation: {d.relevance_explanation[:110]}...")
            print(f"       Subdomains:  {d.subdomains}")
            print(f"       Links:       {d.interdisciplinary_links}")
            print(f"       Evidence:    {len(d.evidence)} citations tracked")

        print(
            f"\n  4.2 Discovered Real-World Problem Candidates ({len(domain_map.problem_candidates)}):"
        )
        for idx, p in enumerate(domain_map.problem_candidates, 1):
            print(f"    {idx}. [{p.domain}] {p.title}")
            print(f"       Affected:    {p.affected_people}")
            print(
                f"       Seriousness: {p.seriousness.value if hasattr(p.seriousness, 'value') else p.seriousness}"
            )
            print(f"       Inadequate:  {p.inadequate_solutions[:2]}")
            print(f"       Opportunity: {p.emerging_opportunities[:2]}")
            print(f"       Citations:   {len(p.evidence)} evidence items")

    # 4.3 Research Sources Tracked
    sources = repo.get_research_sources(session_id)
    print(f"\n  4.3 Research Sources Collected ({len(sources)}):")
    source_counts: dict[str, int] = {}
    for s in sources:
        st = s.get("source_type", "unknown")
        source_counts[st] = source_counts.get(st, 0) + 1
    print(f"      Distribution by connector: {source_counts}")
    print("      Sample Verified Research Citations:")
    for s in sources[:8]:
        print(
            f"        • [{s.get('source_type'):9s}] {s.get('title', '')[:65]} ({s.get('url')})"
        )

    # 4.4 Innovation Gaps
    innovation = result.innovation_report
    if innovation:
        print(f"\n  4.4 Innovation Gaps Analyzed ({len(innovation.gaps)}):")
        for idx, g in enumerate(innovation.gaps, 1):
            classification = (
                g.classification.value
                if hasattr(g.classification, "value")
                else str(g.classification)
            )
            print(
                f"    {idx}. Problem ID: {g.problem_candidate_id} | Class: {classification}"
            )
            print(f"       Gap:             {g.gap_description[:110]}...")
            print(f"       Differentiation: {g.differentiation_potential[:110]}...")
            print(
                f"       Existing Solns:  {len(g.existing_solutions)} solutions compared"
            )

    # ------------------------------------------------------------------
    # Step 5: Adversarial Competition & Winner Selection Audit
    # ------------------------------------------------------------------
    print("\n[PHASE 2 - STEP 5] Adversarial Competition & Quality Gates Audit...")
    evaluations = repo.get_evaluations(session_id)
    debates = repo.get_debate_history(session_id)

    print(f"  Finalists Competing in Adversarial Evaluation: {len(evaluations)}")
    print(f"  Total Debate Rounds Executed:                 {len(debates)}")

    if debates:
        print("\n  5.1 Debate History Across Rounds:")
        for d in debates:
            print(
                f"    • Round {d.get('round_number')} on Candidate {d.get('candidate_id')}:"
            )
            print(
                f"        Score:          {d.get('score_before')} -> {d.get('score_after')} (Adj: {d.get('adjustment', 0):+0.1f})"
            )
            print(f"        Recommendation: {d.get('recommendation')}")
            crit_summary = d.get("criticism", "")[:120].replace("\n", " ")
            print(f"        Criticism:      {crit_summary}...")

    print("\n  5.2 Candidate Evaluations & Deterministic Quality Gates:")
    for idx, ev in enumerate(evaluations, 1):
        cand_id = ev.get("candidate_id")
        gates = ev.get("gates_json") or []
        scores = ev.get("scores_json") or []
        passed_gates = sum(1 for g in gates if g.get("status") == "passed")
        print(f"\n  --- Finalist {idx}: ID {cand_id} ---")
        print(
            f"    Total Score:          {ev.get('total_score')}/100 (Rank: {ev.get('rank')})"
        )
        print(f"    Qualified:            {bool(ev.get('is_qualified'))}")
        print(
            f"    All Gates Passed:     {bool(ev.get('all_gates_passed'))} ({passed_gates}/{len(gates)} passed)"
        )
        print(f"    Assessment:           {ev.get('assessment', '')[:140]}...")

        print("    Criterion Scores:")
        for sc in scores:
            print(
                f"      • {sc.get('name', 'criterion'):30s}: {sc.get('score', 0):4.1f} / {sc.get('weight', 0):2d} pts | {sc.get('justification', '')[:60]}..."
            )

        print("    Quality Gates Breakdown:")
        for g in gates:
            status_icon = "PASS" if g.get("status") == "passed" else "FAIL"
            print(f"      [{status_icon:4s}] Gate '{g.get('name')}': {g.get('reason')}")

    print("\n  5.3 Final Selection Outcome:")
    if result.winner and result.winner.has_winner:
        w = result.winner
        print(f"    WINNER:             {w.winner.candidate_title}")
        print(f"    Domain:             {w.winner.domain}")
        print(f"    Winning Score:      {w.winner.total_score:.1f}/100")
        print(f"    Assessment:         {w.winner.overall_assessment[:140]}...")
        print(f"    Selection Method:   {w.selection_methodology[:140]}...")
        print(f"    Debate Summary:     {w.debate_summary[:140]}...")
    else:
        print(
            "    RESULT: Honest Rejection — No candidate satisfied all mandatory quality gates."
        )
        reason = (
            result.winner.rejection_reason
            if result.winner
            else "No finalists qualified"
        )
        print(f"    Rejection Reason: {reason}")

    # ------------------------------------------------------------------
    # Step 6: Hardware Performance & Resource Measurements
    # ------------------------------------------------------------------
    print("\n[PHASE 2 - STEP 6] Hardware Performance & Model Metrics...")
    ram_final_used, ram_final_total, ram_final_pct = get_system_ram_mb()
    gpu_final_used, gpu_final_total = get_gpu_vram_mb()

    llm_stats = client.stats.as_dict()
    print(f"  Total Wall-Clock Time:   {t_total:.2f}s ({t_total / 60:.2f} min)")
    print(
        f"  Total LLM Invocations:   {llm_stats.get('calls')} calls ({llm_stats.get('failures')} failures)"
    )
    print(f"  Total LLM Compute Time:  {llm_stats.get('total_seconds'):.2f}s")
    print(f"  Total Prompt Characters: {llm_stats.get('prompt_chars'):,}")
    print(f"  Total Output Characters: {llm_stats.get('response_chars'):,}")

    avg_latency = (
        llm_stats.get("total_seconds") / llm_stats.get("calls")
        if llm_stats.get("calls")
        else 0
    )
    est_tok_per_sec = (
        (llm_stats.get("response_chars", 0) / 4.0) / llm_stats.get("total_seconds")
        if llm_stats.get("total_seconds")
        else 0
    )
    print(f"  Average Latency per Call:{avg_latency:.2f}s")
    print(f"  Estimated Output Speed:  {est_tok_per_sec:.1f} tokens/sec")
    print(
        f"  System RAM Peak Delta:   {ram_final_used - ram_init_used:+.1f} MB (Current: {ram_final_used} MB / {ram_final_total} MB, {ram_final_pct}% load)"
    )
    print(
        f"  GPU VRAM Delta:          {gpu_final_used - gpu_init_used:+} MiB (Current: {gpu_final_used} MiB / {gpu_final_total} MiB)"
    )

    # ------------------------------------------------------------------
    # Step 7: Generated Final Report Verification
    # ------------------------------------------------------------------
    print("\n[PHASE 2 - STEP 7] Final Report Artifact Verification...")
    report_files = list((ROOT / "data" / "reports").glob(f"*{session_id[:8]}*"))
    print(
        f"  Report Files on Disk:    {len(report_files)} -> {[f.name for f in report_files]}"
    )
    for rf in report_files:
        print(f"    - {rf.name}: {rf.stat().st_size:,} bytes")

    print("\n" + "=" * 76)
    print("  PHASE 2 REAL-WORLD EVALUATION COMPLETE")
    print("=" * 76)


if __name__ == "__main__":
    main()
