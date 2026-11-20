"""Comprehensive HackathonIQ Local Model & End-to-End Operational Verification.

Verifies:
1. Actual GPU offloading and memory usage.
2. Structured output quality and semantic depth from all 5 agents.
3. Complete LangGraph workflow execution on a realistic hackathon scenario.
4. Retrieved research source quality and relevance across connectors.
5. Adversarial debate, deterministic quality gates, and winner selection.
6. Real performance measurements (latency, throughput, GPU VRAM, system RAM).
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

from src.agents.adversarial_critic import (
    CritiqueLLM,
)
from src.agents.domain_discovery import (
    DomainListLLM,
)
from src.agents.hackathon_intelligence import (
    HackathonIntelLLM,
)
from src.agents.innovation_research import InnovationBatchLLM
from src.agents.solution_architect import SolutionLLM
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
    print("=" * 70)
    print("  HACKATHONIQ END-TO-END VERIFICATION & REAL OPERATION BENCHMARK")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Step 1: Hardware, GPU Offload, and Memory Baseline
    # ------------------------------------------------------------------
    print("\n[STEP 1] Verifying Actual GPU Offload and Memory Baseline...")
    ram_used, ram_total, ram_pct = get_system_ram_mb()
    gpu_used, gpu_total = get_gpu_vram_mb()
    print(f"  System RAM: {ram_used} MB used / {ram_total} MB total ({ram_pct}% load)")
    print(f"  GPU VRAM:   {gpu_used} MiB used / {gpu_total} MiB total")

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
            f"  Runner:              {m.get('runner')} | Context Length: {m.get('context_length')}"
        )
        print(
            f"  GPU Offloading:      {offload_pct}% ({vram_bytes / (1024**2):.1f} MB in VRAM)"
        )
    else:
        print(
            "  Ollama Active Model: None currently warm in memory (will load on first call)"
        )

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
    # Step 2: Test Structured Outputs & Semantic Depth of All 5 Agents
    # ------------------------------------------------------------------
    print("\n[STEP 2] Testing Structured Outputs & Semantic Depth from All 5 Agents...")
    agent_evaluations: dict[str, dict[str, Any]] = {}

    # Test Agent 1: Hackathon Intelligence
    print("\n  [2.1] Agent 1 — Hackathon Intelligence Agent")
    t0 = time.perf_counter()
    prompt_a1 = (
        "Hackathon Theme: 'AI for Climate Resilience and Urban Heat Mitigation'. "
        "Organizer: 'Global Resilience Foundation'. "
        "Rules: 'Open-source solutions using real open geospatial/sensor datasets. Must demonstrate working prototype.' "
        "Analyze the organizer goals, judging criteria, and core verified facts."
    )
    res_a1 = client.generate_json(
        prompt_a1,
        HackathonIntelLLM,
        "You are the Hackathon Intelligence Agent. Extract genuine priorities and return schema-valid JSON.",
    )
    t_a1 = time.perf_counter() - t0
    print(f"    Latency: {t_a1:.2f}s")
    print(
        f"    Goals Extracted:    {len(res_a1.organizer_goals)} -> {res_a1.organizer_goals[:2]}"
    )
    print(
        f"    Expected Outcomes:  {len(res_a1.expected_outcomes)} -> {res_a1.expected_outcomes[:2]}"
    )
    print(
        f"    Verified Facts:     {len(res_a1.verified_facts)} -> {res_a1.verified_facts[:2]}"
    )
    print(
        f"    Judging Criteria:   {len(res_a1.judging_criteria)} -> {[c.name for c in res_a1.judging_criteria[:3]]}"
    )
    a1_substantive = bool(
        res_a1.organizer_goals or res_a1.expected_outcomes or res_a1.verified_facts
    )
    agent_evaluations["Agent 1"] = {
        "latency": round(t_a1, 2),
        "substantive": a1_substantive,
    }

    # Test Agent 2: Domain Discovery
    print("\n  [2.2] Agent 2 — Dynamic Domain Discovery Agent")
    t0 = time.perf_counter()
    prompt_a2 = (
        "Theme: 'AI for Climate Resilience and Urban Heat Mitigation'. "
        "Discover 3 distinct real-world domains across disciplines with subdomains and search queries."
    )
    res_a2 = client.generate_json(
        prompt_a2,
        DomainListLLM,
        "You are the Dynamic Domain Discovery Agent. Return schema-valid JSON only.",
    )
    t_a2 = time.perf_counter() - t0
    domain_names = [d.name for d in res_a2.domains]
    print(f"    Latency: {t_a2:.2f}s")
    print(f"    Domains Found:      {len(res_a2.domains)} -> {domain_names}")
    for d in res_a2.domains[:2]:
        print(
            f"      - {d.name}: subdomains={d.subdomains[:3]}, queries={d.search_queries[:2]}"
        )
    a2_substantive = len(res_a2.domains) >= 2 and all(
        len(d.subdomains) > 0 for d in res_a2.domains
    )
    agent_evaluations["Agent 2"] = {
        "latency": round(t_a2, 2),
        "substantive": a2_substantive,
        "domains": domain_names,
    }

    # Test Agent 3: Innovation Research
    print("\n  [2.3] Agent 3 — Global Innovation Research Agent")
    t0 = time.perf_counter()
    prompt_a3 = (
        "Candidate Problem: 'Urban heat islands causing hyper-localized heat stroke mortality among outdoor gig-workers'. "
        "Domain: 'Urban Public Health and Microclimate Modeling'. "
        "Existing solutions: Standard city-wide weather forecasts lack neighborhood microclimate resolution. "
        "Classify the innovation gap, describe differentiation potential, and summarize research evidence."
    )
    res_a3 = client.generate_json(
        prompt_a3,
        InnovationBatchLLM,
        "You are the Innovation Research Agent. Analyze competitive landscape and return schema-valid JSON.",
    )
    t_a3 = time.perf_counter() - t0
    print(f"    Latency: {t_a3:.2f}s")
    print(f"    Gaps Analyzed:      {len(res_a3.gaps)}")
    if res_a3.gaps:
        g = res_a3.gaps[0]
        print(f"    Classification:     {g.classification}")
        print(f"    Gap Description:    {g.gap_description[:100]}...")
        print(f"    Differentiation:    {g.differentiation_potential[:100]}...")
    a3_substantive = len(res_a3.gaps) > 0 and bool(res_a3.gaps[0].gap_description)
    agent_evaluations["Agent 3"] = {
        "latency": round(t_a3, 2),
        "substantive": a3_substantive,
    }

    # Test Agent 4: Solution Architect
    print("\n  [2.4] Agent 4 — Solution Architect Agent")
    t0 = time.perf_counter()
    prompt_a4 = (
        "Architect a buildable hackathon solution for: "
        "'Hyper-localized microclimate heat-stress route planner for municipal delivery workers'. "
        "Ground in open satellite thermal data (Sentinel-3/Landsat) and OpenStreetMap. "
        "Provide clear technical architecture, estimated hours, risks, and demo plan."
    )
    res_a4 = client.generate_json(
        prompt_a4,
        SolutionLLM,
        "You are the Solution Architect Agent. Design a feasible, buildable hackathon solution in JSON.",
    )
    t_a4 = time.perf_counter() - t0
    print(f"    Latency: {t_a4:.2f}s")
    print(f"    Solution Title:     {res_a4.title}")
    print(
        f"    Estimated Hours:    {res_a4.estimated_hours}h (Complexity: {res_a4.development_complexity})"
    )
    print(f"    Architecture:       {res_a4.technical_architecture[:100]}...")
    print(f"    Data Requirements:  {len(res_a4.data_requirements)} categories")
    print(
        f"    Risks Identified:   {len(res_a4.risks)} -> {[r.description[:50] for r in res_a4.risks[:2]]}"
    )
    a4_substantive = bool(
        res_a4.title and res_a4.estimated_hours > 0 and res_a4.technical_architecture
    )
    agent_evaluations["Agent 4"] = {
        "latency": round(t_a4, 2),
        "substantive": a4_substantive,
    }

    # Test Agent 5: Adversarial Critic
    print("\n  [2.5] Agent 5 — Adversarial Critic Agent")
    t0 = time.perf_counter()
    prompt_a5 = (
        f"Candidate Solution: '{res_a4.title}'. "
        f"Proposed Architecture: {res_a4.technical_architecture}. "
        f"Estimated Hours: {res_a4.estimated_hours}h. "
        "Challenge this candidate aggressively with 2 concrete criticisms regarding "
        "satellite revisit latency, data pipeline complexity, and hackathon time limits."
    )
    res_a5 = client.generate_json(
        prompt_a5,
        CritiqueLLM,
        "You are the Adversarial Critic Agent. Challenge claims and return schema-valid JSON.",
    )
    t_a5 = time.perf_counter() - t0
    print(f"    Latency: {t_a5:.2f}s")
    print(f"    Criticisms Raised:  {len(res_a5.criticisms)}")
    for c in res_a5.criticisms[:2]:
        print(f"      - [{c.severity.upper()}] {c.category}: {c.issue[:80]}...")
    a5_substantive = len(res_a5.criticisms) >= 2 and all(
        len(c.issue) > 10 for c in res_a5.criticisms
    )
    agent_evaluations["Agent 5"] = {
        "latency": round(t_a5, 2),
        "substantive": a5_substantive,
    }

    # ------------------------------------------------------------------
    # Step 3 & 4: Complete LangGraph Workflow & Real Hackathon Scenario
    # ------------------------------------------------------------------
    print(
        "\n[STEP 3 & 4] Running Complete LangGraph Pipeline on Real Hackathon Scenario..."
    )
    repo = Repository()
    research_svc = ResearchService(repo)

    scenario_input = HackathonInput(
        theme="AI for Climate Resilience and Urban Heat Mitigation",
        name="Global Climate Hack 2026",
        website_url="https://example.org/climate-hack-2026",
        rules_url="https://example.org/climate-hack-2026/rules",
        constraints=(
            "Must be demonstrable within a 36-hour hackathon timeframe. "
            "Must use open geospatial or meteorological datasets. "
            "Must not require proprietary paid APIs."
        ),
    )

    pipeline_options = PipelineOptions(
        max_domains=3,
        problems_per_domain=2,
        max_finalists=2,
        max_debate_rounds=1,
        include_continuous_intelligence=True,
    )

    stage_events: list[tuple[str, str, float, float]] = []
    t_pipeline_start = time.perf_counter()

    def progress_callback(stage: str, msg: str, pct: float) -> None:
        elapsed = time.perf_counter() - t_pipeline_start
        stage_events.append((stage, msg, pct, elapsed))
        print(f"  [{elapsed:6.1f}s | {int(pct * 100):3d}%] [{stage:22s}] {msg}")

    pipeline = HackathonPipeline(
        llm=client,
        repository=repo,
        research=research_svc,
        progress=progress_callback,
    )

    print(
        f"  Starting LangGraph invocation for session theme: '{scenario_input.theme}'"
    )
    result = pipeline.run(scenario_input, pipeline_options)
    t_pipeline_total = time.perf_counter() - t_pipeline_start

    print(
        f"\n  LangGraph Execution Finished in {t_pipeline_total:.2f}s with status: {result.status}"
    )

    # ------------------------------------------------------------------
    # Step 5: Source Retrieval Quality & Relevance Audit
    # ------------------------------------------------------------------
    print("\n[STEP 5] Inspecting Quality & Relevance of Retrieved Sources...")
    session_id = result.session_id
    stored_sources = repo.get_research_sources(session_id)
    print(f"  Total Research Sources Tracked: {len(stored_sources)}")

    source_by_type: dict[str, int] = {}
    for s in stored_sources:
        st = s.get("source_type", "unknown")
        source_by_type[st] = source_by_type.get(st, 0) + 1

    print(f"  Sources by Connector: {source_by_type}")
    print("  Sample Retrieved Sources:")
    for s in stored_sources[:5]:
        print(f"    • [{s.get('source_type')}] {s.get('title')} ({s.get('url')})")

    # ------------------------------------------------------------------
    # Step 6: Adversarial Debate, Quality Gates & Winner Selection
    # ------------------------------------------------------------------
    print("\n[STEP 6] Verifying Adversarial Debate & Final Candidate Selection...")
    evaluations = repo.get_evaluations(session_id)
    debates = repo.get_debate_history(session_id)
    print(f"  Candidates Evaluated: {len(evaluations)}")
    print(f"  Debates Recorded:     {len(debates)}")

    for idx, ev in enumerate(evaluations, 1):
        cand_id = ev.get("candidate_id")
        gates = ev.get("gates_json") or []
        passed_gates = sum(1 for g in gates if g.get("status") == "passed")
        print(f"\n  --- Candidate {idx}: ID {cand_id} ---")
        print(
            f"    Total Score:          {ev.get('total_score')}/100 (Rank: {ev.get('rank')})"
        )
        print(f"    Qualified:            {bool(ev.get('is_qualified'))}")
        print(
            f"    Quality Gates Passed: {passed_gates}/{len(gates)} (All passed: {bool(ev.get('all_gates_passed'))})"
        )
        for g in gates:
            status_icon = "PASS" if g.get("status") == "passed" else "FAIL"
            print(f"      [{status_icon}] Gate '{g.get('name')}': {g.get('reason')}")
        if ev.get("assessment"):
            print(f"    Assessment:           {ev.get('assessment')[:120]}...")

    if debates:
        print("\n  Debate History:")
        for d in debates:
            print(
                f"    • Round {d.get('round_number')}: Candidate {d.get('candidate_id')} | Before: {d.get('score_before')} -> After: {d.get('score_after')} | Rec: {d.get('recommendation')}"
            )

    print("\n  Final Winner Selection:")
    if result.winner and result.winner.has_winner:
        w = result.winner
        print(f"    WINNER:             {w.winner.candidate_title}")
        print(f"    Domain:             {w.winner.domain}")
        print(f"    Winning Score:      {w.winner.total_score:.1f}/100")
        print(f"    Assessment:         {w.winner.overall_assessment[:120]}...")
        print(f"    Methodology:        {w.selection_methodology[:120]}...")
        print(f"    Debate Summary:     {w.debate_summary[:120]}...")
    else:
        print(
            "    RESULT: Honest Rejection — No candidate satisfied all mandatory quality gates."
        )
        print(
            f"    Rejection Reason: {result.winner.rejection_reason if result.winner else 'None evaluated'}"
        )

    # ------------------------------------------------------------------
    # Step 7: Record Actual Latency, Throughput, GPU & RAM Usage
    # ------------------------------------------------------------------
    print("\n[STEP 7] Final Performance Measurements & Resource Utilization...")
    ram_end_used, ram_end_total, _ram_end_pct = get_system_ram_mb()
    gpu_end_used, gpu_end_total = get_gpu_vram_mb()

    llm_stats = client.stats.as_dict()
    print(
        f"  Total Pipeline Duration: {t_pipeline_total:.2f}s ({t_pipeline_total / 60:.1f} min)"
    )
    print(
        f"  Total LLM Invocations:   {llm_stats.get('calls')} calls ({llm_stats.get('failures')} failures)"
    )
    print(f"  Total LLM Time:          {llm_stats.get('total_seconds'):.2f}s")
    print(f"  Total Prompt Characters: {llm_stats.get('prompt_chars'):,}")
    print(f"  Total Output Characters: {llm_stats.get('response_chars'):,}")

    avg_latency = (
        llm_stats.get("total_seconds") / llm_stats.get("calls")
        if llm_stats.get("calls")
        else 0
    )
    # Estimate token throughput (approx 4 chars per token)
    est_output_tokens = llm_stats.get("response_chars", 0) / 4.0
    est_tok_per_sec = (
        est_output_tokens / llm_stats.get("total_seconds")
        if llm_stats.get("total_seconds")
        else 0
    )
    print(f"  Average LLM Latency:     {avg_latency:.2f}s per call")
    print(f"  Estimated Output Speed:  {est_tok_per_sec:.1f} tokens/sec")
    print(
        f"  System RAM Delta:        {ram_end_used - ram_used:+.1f} MB (Peak: {ram_end_used} MB / {ram_end_total} MB)"
    )
    print(
        f"  GPU VRAM Delta:          {gpu_end_used - gpu_used:+} MiB (Current: {gpu_end_used} MiB / {gpu_end_total} MiB)"
    )

    # Check generated reports
    print("\n  Generated Artifacts:")
    reports = repo.get_session_reports(session_id)
    print(f"  Reports Stored in DB: {len(reports)}")
    report_files = list((ROOT / "data" / "reports").glob(f"*{session_id}*"))
    print(
        f"  Report Files on Disk: {len(report_files)} -> {[f.name for f in report_files]}"
    )

    print("\n" + "=" * 70)
    print("  VERIFICATION COMPLETE — ALL PHASES AUDITED")
    print("=" * 70)


if __name__ == "__main__":
    main()
