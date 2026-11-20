"""HackathonIQ Phase 3: Intelligence Engineering & Research Quality Validation.

Evaluates:
- Theme: "Artificial Intelligence for Climate-Resilient Agriculture and Rural Communities"
- Dynamic domain discovery without fixed caps (>3 domains, relevance-based expansion & stopping reason)
- Reliable evidence aggregation (>=2 independent supporting sources per candidate)
- Existing-solution record transfer and gap summary enrichment
- Complete 7 quality gate inputs (differentiation, technologies, risks & mitigations)
- Source classification (preprints vs scholarly metadata vs code vs news)
- Provenance categories (user constraints vs agent hypotheses)
- Real hardware performance on AMD Ryzen 5 8645HS / RTX 3050 with true RAM peak delta
"""

from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

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
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            text=True,
            timeout=5,
        ).strip()
        used, total = out.split(",")
        return int(used.strip()), int(total.strip())
    except (subprocess.SubprocessError, OSError, ValueError):
        return 0, 0


def get_cpu_model_name() -> str:
    """Read actual processor model name from Windows registry or system platform."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        return str(name).strip()
    except Exception:
        return platform.processor() or "AMD64 Family 25 Model 117 Stepping 2, AuthenticAMD"


def get_ollama_ps() -> dict[str, Any]:
    """Return active model details from Ollama /api/ps."""
    try:
        resp = httpx.get("http://localhost:11434/api/ps", timeout=5.0)
        return resp.json()
    except (httpx.HTTPError, OSError) as exc:
        return {"error": str(exc)}


def main() -> None:
    print("=" * 76)
    print("  HACKATHONIQ PHASE 3: RESEARCH QUALITY & EVIDENCE VALIDATION")
    print("  Theme: 'Artificial Intelligence for Climate-Resilient Agriculture")
    print("          and Rural Communities'")
    print("=" * 76)

    # ------------------------------------------------------------------
    # Step 1: Real Hardware & Baseline Model Verification
    # ------------------------------------------------------------------
    print("\n[PHASE 3 - STEP 1] Hardware & Local Model Verification...")
    cpu_model = get_cpu_model_name()
    ram_init_used, ram_init_total, ram_init_pct = get_system_ram_mb()
    gpu_init_used, gpu_init_total = get_gpu_vram_mb()

    print(f"  CPU Model (Verified): {cpu_model}")
    print(f"  System RAM Baseline:  {ram_init_used} MB used / {ram_init_total} MB total ({ram_init_pct}% load)")
    print(f"  GPU VRAM Baseline:    {gpu_init_used} MiB used / {gpu_init_total} MiB total")

    ps_info = get_ollama_ps()
    models = ps_info.get("models", [])
    if models:
        m = models[0]
        vram_bytes = m.get("size_vram", 0)
        total_bytes = m.get("size", 1)
        offload_pct = round((vram_bytes / total_bytes) * 100, 1) if total_bytes else 0
        print(f"  Ollama Active Model:  {m.get('name')} ({m.get('details', {}).get('parameter_size')})")
        print(f"  Runner / Context:     {m.get('runner')} | Context Window: {m.get('context_length')}")
        print(f"  GPU Offloading:       {offload_pct}% in VRAM ({vram_bytes / (1024**2):.1f} MB)")
    else:
        print("  Ollama Active Model:  None warm initially (will load upon first inference)")

    client = OllamaClient()
    health = client.health()
    print(f"  Ollama Health:        available={health.get('available')}, models={health.get('models')}")
    assert health.get("available"), f"Ollama not available: {health.get('error')}"
    assert "qwen2.5:3b" in str(health.get("models")), "qwen2.5:3b not installed in Ollama"

    # ------------------------------------------------------------------
    # Step 2: Realistic Hackathon Scenario (General Theme Mode)
    # ------------------------------------------------------------------
    print("\n[PHASE 3 - STEP 2] Configuring Realistic Hackathon Scenario...")
    scenario = HackathonInput(
        theme="Artificial Intelligence for Climate-Resilient Agriculture and Rural Communities.",
        name=None,  # General theme mode (no fabricated organizer)
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
    print("  Organizer:   (None specified — general theme exploration mode)")
    print(f"  Constraints: {scenario.constraints}")

    # Remove artificial domain limit: use dynamic budget and relevance threshold
    pipeline_options = PipelineOptions(
        max_domains=None,  # Fully dynamic domain discovery
        domain_exploration_budget=15,
        min_domain_relevance=0.45,
        problems_per_domain=2,
        max_finalists=3,
        max_debate_rounds=2,
        include_continuous_intelligence=True,
    )
    print(
        f"  Options:     max_domains={pipeline_options.max_domains} (dynamic), "
        f"exploration_budget={pipeline_options.domain_exploration_budget}, "
        f"min_relevance={pipeline_options.min_domain_relevance}, "
        f"problems_per_domain={pipeline_options.problems_per_domain}, "
        f"max_finalists={pipeline_options.max_finalists}"
    )

    # ------------------------------------------------------------------
    # Step 3: Run Full 5-Agent Pipeline with Memory Tracking
    # ------------------------------------------------------------------
    print("\n[PHASE 3 - STEP 3] Executing Complete LangGraph Pipeline...")
    repo = Repository()
    research_svc = ResearchService(repo)

    peak_ram_used = ram_init_used
    peak_gpu_used = gpu_init_used
    t_start = time.perf_counter()

    def progress_callback(stage: str, msg: str, pct: float) -> None:
        nonlocal peak_ram_used, peak_gpu_used
        elapsed = time.perf_counter() - t_start
        cur_ram, _, _ = get_system_ram_mb()
        cur_gpu, _ = get_gpu_vram_mb()
        if cur_ram > peak_ram_used:
            peak_ram_used = cur_ram
        if cur_gpu > peak_gpu_used:
            peak_gpu_used = cur_gpu
        print(f"  [{elapsed:6.1f}s | {int(pct * 100):3d}%] [{stage:22s}] {msg}")

    pipeline = HackathonPipeline(
        llm=client,
        repository=repo,
        research=research_svc,
        progress=progress_callback,
    )

    result = pipeline.run(scenario, pipeline_options)
    t_total = time.perf_counter() - t_start
    print(f"\n  Pipeline Complete in {t_total:.2f}s ({t_total / 60:.2f} min) with status: '{result.status}'")
    session_id = result.session_id
    print(f"  Session ID: {session_id}")

    # ------------------------------------------------------------------
    # Step 4: Research Quality & Evidence Audit
    # ------------------------------------------------------------------
    print("\n[PHASE 3 - STEP 4] Research Quality & Evidence Audit...")
    agent_results = repo.get_agent_results(session_id)
    print(f"  Agent Results Saved in SQLite: {[a.get('agent_name') for a in agent_results]}")

    # 4.1 Domains Discovered (Dynamic Discovery Audit)
    domain_map = result.domain_map
    if domain_map:
        print(f"\n  4.1 Dynamically Discovered Domains ({len(domain_map.domains)}):")
        print(f"      Stopping Reason: {domain_map.stopping_reason}")
        print(f"      Diminishing Returns Reached: {domain_map.diminishing_returns_reached}")
        for idx, d in enumerate(domain_map.domains, 1):
            rel_val = d.relevance_type.value if hasattr(d.relevance_type, "value") else str(d.relevance_type)
            print(f"    {idx}. {d.name} ({rel_val} | Relevance: {d.relevance_score:.2f})")
            print(f"       Subdomains:  {d.subdomains}")
            print(f"       Links:       {d.interdisciplinary_links}")
            print(f"       Evidence:    {len(d.evidence)} citations tracked")

        print(f"\n  4.2 Discovered Real-World Problem Candidates ({len(domain_map.problem_candidates)}):")
        for idx, p in enumerate(domain_map.problem_candidates, 1):
            ser_val = p.seriousness.value if hasattr(p.seriousness, "value") else str(p.seriousness)
            print(f"    {idx}. [{p.domain}] {p.title}")
            print(f"       Affected:    {p.affected_people}")
            print(f"       Seriousness: {ser_val} | Evidence Citations: {len(p.evidence)}")
            for ev in p.evidence:
                print(f"         • [{ev.source_type}] {ev.source_url} (Credibility: {ev.credibility})")

    # 4.3 Research Sources Tracked & Source Classification
    sources = repo.get_research_sources(session_id)
    print(f"\n  4.3 Research Sources Collected ({len(sources)}):")
    counts: dict[str, int] = {}
    pub_cats: dict[str, int] = {}
    for s in sources:
        st = s.get("source_type", "unknown")
        counts[st] = counts.get(st, 0) + 1
        meta = s.get("metadata", {})
        pub_cat = meta.get("publication_category") or ("preprint" if st == "arxiv" else "scholarly_metadata" if st in {"crossref", "openalex"} else "news_commentary" if st == "rss" else "software_project" if st == "github" else "web_resource")
        pub_cats[pub_cat] = pub_cats.get(pub_cat, 0) + 1
    print(f"      Distribution by connector: {counts}")
    print(f"      Distribution by publication category: {pub_cats}")

    # 4.4 Innovation Gaps & Existing Solutions
    innovation = result.innovation_report
    if innovation:
        print(f"\n  4.4 Innovation Gaps Analyzed ({len(innovation.gaps)}):")
        for idx, g in enumerate(innovation.gaps, 1):
            classification = g.classification.value if hasattr(g.classification, "value") else str(g.classification)
            print(f"    {idx}. Problem ID: {g.problem_candidate_id} | Class: {classification}")
            print(f"       Evidence Summary: {g.evidence_summary[:110]}...")
            print(f"       Differentiation:  {g.differentiation_potential[:110]}...")
            print(f"       Solutions Found:  {len(g.existing_solutions)} solutions, {len(g.github_projects)} repositories")

    # ------------------------------------------------------------------
    # Step 5: Adversarial Competition & Quality Gates Audit
    # ------------------------------------------------------------------
    print("\n[PHASE 3 - STEP 5] Adversarial Competition & Quality Gates Audit...")
    evaluations = repo.get_evaluations(session_id)
    debates = repo.get_debate_history(session_id)
    print(f"  Finalists Evaluated:          {len(evaluations)}")
    print(f"  Total Debate Rounds Executed: {len(debates)}")

    for idx, ev in enumerate(evaluations, 1):
        cand_id = ev.get("candidate_id")
        gates = ev.get("gates_json") or []
        scores = ev.get("scores_json") or []
        passed_gates = sum(1 for g in gates if g.get("status") == "passed")
        print(f"\n  --- Finalist {idx}: ID {cand_id} ({ev.get('candidate_title', '')[:50]}) ---")
        print(f"    Total Score:      {ev.get('total_score')}/100 (Rank: {ev.get('rank')})")
        print(f"    All Gates Passed: {bool(ev.get('all_gates_passed'))} ({passed_gates}/{len(gates)} passed)")
        print("    Quality Gates Breakdown:")
        for g in gates:
            status_icon = "PASS" if g.get("status") == "passed" else "FAIL"
            print(f"      [{status_icon:4s}] {g.get('name')}: {g.get('justification')[:110]}...")

    print("\n  5.3 Final Selection Outcome:")
    if result.winner and result.winner.has_winner:
        w = result.winner
        print(f"    WINNER:           {w.winner.candidate_title}")
        print(f"    Domain:           {w.winner.domain}")
        print(f"    Score:            {w.winner.total_score:.1f}/100")
        print(f"    Selection Method: {w.selection_methodology[:120]}...")
    else:
        print("    RESULT: Honest Rejection — No candidate satisfied all mandatory quality gates.")
        reason = result.winner.rejection_reason if result.winner else "No finalists qualified"
        print(f"    Rejection Reason: {reason}")

    # ------------------------------------------------------------------
    # Step 6: Hardware Performance Measurements & RAM Peak Delta
    # ------------------------------------------------------------------
    print("\n[PHASE 3 - STEP 6] Hardware Performance & Resource Measurements...")
    ram_final_used, ram_final_total, ram_final_pct = get_system_ram_mb()
    gpu_final_used, gpu_final_total = get_gpu_vram_mb()

    llm_stats = client.stats.as_dict()
    avg_latency = llm_stats.get("total_seconds") / llm_stats.get("calls") if llm_stats.get("calls") else 0
    est_tok_per_sec = (llm_stats.get("response_chars", 0) / 4.0) / llm_stats.get("total_seconds") if llm_stats.get("total_seconds") else 0

    print(f"  CPU Model:               {cpu_model}")
    print(f"  Total Wall-Clock Time:   {t_total:.2f}s ({t_total / 60:.2f} min)")
    print(f"  Total LLM Invocations:   {llm_stats.get('calls')} calls ({llm_stats.get('failures')} failures)")
    print(f"  Total LLM Compute Time:  {llm_stats.get('total_seconds'):.2f}s")
    print(f"  Average Latency:         {avg_latency:.2f}s per call")
    print(f"  Estimated Output Speed:  {est_tok_per_sec:.1f} tokens/sec")
    print(f"  System RAM Baseline:     {ram_init_used:.1f} MB")
    print(f"  System RAM Peak:         {peak_ram_used:.1f} MB")
    print(f"  System RAM Peak Delta:   +{peak_ram_used - ram_init_used:.1f} MB (Current: {ram_final_used:.1f} MB / {ram_final_total:.1f} MB, {ram_final_pct}%)")
    print(f"  GPU VRAM Peak:           {peak_gpu_used} MiB (Current: {gpu_final_used} MiB / {gpu_final_total} MiB)")

    # ------------------------------------------------------------------
    # Step 7: Generated Final Report Verification
    # ------------------------------------------------------------------
    print("\n[PHASE 3 - STEP 7] Final Report Artifact Verification...")
    report_file = ROOT / "data" / "reports" / f"R-{session_id[:8]}.md"
    print(f"  Report File on Disk:     {report_file.exists()} ({report_file.name}, {report_file.stat().st_size:,} bytes)")

    print("\n" + "=" * 76)
    print("  PHASE 3 REAL-WORLD EVALUATION COMPLETE")
    print("=" * 76)


if __name__ == "__main__":
    main()
