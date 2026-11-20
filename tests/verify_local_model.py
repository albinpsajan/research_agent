"""Verification script for local model integration, performance, and multi-agent sharing."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.adversarial_critic import CritiqueLLM
from src.agents.domain_discovery import DomainListLLM
from src.agents.hackathon_intelligence import HackathonIntelLLM
from src.agents.innovation_research import InnovationBatchLLM
from src.agents.solution_architect import SolutionLLM
from src.llm.client import OllamaClient


def get_gpu_vram_mb() -> tuple[int, int]:
    """Return (used_mb, total_mb) of dedicated GPU VRAM via nvidia-smi."""
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


def run_verification() -> dict[str, Any]:
    print("==================================================")
    print(" HackathonIQ Local Model Verification & Benchmark ")
    print("==================================================")

    client = OllamaClient()
    health = client.health()
    print(
        f"Ollama Health: available={health.get('available')}, models={health.get('models')}"
    )
    if not health.get("available") or not health.get("models"):
        print("ERROR: Ollama is not available or has no models installed.")
        return {"success": False, "error": "Ollama not ready"}

    resolved_model = client.resolve_model()
    print(f"Active Resolved Model: {resolved_model}")

    gpu_before, gpu_total = get_gpu_vram_mb()
    print(f"Baseline Dedicated GPU VRAM: {gpu_before} MiB used / {gpu_total} MiB total")

    # --- Test 1: Basic Inference & Latency ---
    print("\n--- Test 1: Basic Inference & Smoke Latency ---")
    t0 = time.perf_counter()
    resp = client._http.post(
        "/api/generate",
        json={
            "model": resolved_model,
            "prompt": "Say 'ready' in one word.",
            "stream": False,
        },
        timeout=60,
    ).json()
    t_smoke = time.perf_counter() - t0
    smoke_eval_count = resp.get("eval_count", 0)
    smoke_eval_duration_ms = resp.get("eval_duration", 1) / 1e6
    smoke_tok_per_sec = (
        (smoke_eval_count / (smoke_eval_duration_ms / 1000))
        if smoke_eval_duration_ms > 0
        else 0
    )
    print(f"Response: {resp.get('response', '').strip()}")
    print(f"Smoke Latency: {t_smoke:.2f}s (Tokens/sec: {smoke_tok_per_sec:.1f})")

    gpu_loaded, _ = get_gpu_vram_mb()
    print(
        f"GPU VRAM after model load: {gpu_loaded} MiB used (Delta: +{gpu_loaded - gpu_before} MiB)"
    )

    # --- Test 2: Multi-Agent Schema Sharing ---
    print("\n--- Test 2: Verifying All 5 Logical Agents Share This Model ---")

    results = {}

    # Agent 1 Schema: HackathonIntelLLM
    print("Testing Agent 1 schema (HackathonIntelLLM)...")
    t_start = time.perf_counter()
    a1_result = client.generate_json(
        "Theme: Clean Energy. Organizer: Tech Foundation. Extract organizer goals, judging criteria, and verified facts.",
        HackathonIntelLLM,
        "You are the Hackathon Intelligence Agent. Return schema-valid JSON only.",
    )
    t_a1 = time.perf_counter() - t_start
    print(
        f"  Agent 1 OK in {t_a1:.2f}s. Goals: {len(a1_result.organizer_goals)}, Facts: {len(a1_result.verified_facts)}"
    )
    results["agent1"] = {"success": True, "time_s": round(t_a1, 2)}

    # Agent 2 Schema: DomainListLLM
    print("Testing Agent 2 schema (DomainListLLM)...")
    t_start = time.perf_counter()
    a2_result = client.generate_json(
        "Theme: Clean Energy. Discover 3 relevant domains across disciplines with subdomains and search queries.",
        DomainListLLM,
        "You are the Dynamic Domain Discovery Agent. Return schema-valid JSON only.",
    )
    t_a2 = time.perf_counter() - t_start
    print(
        f"  Agent 2 OK in {t_a2:.2f}s. Domains found: {[d.name for d in a2_result.domains]}"
    )
    results["agent2"] = {
        "success": True,
        "time_s": round(t_a2, 2),
        "domains": len(a2_result.domains),
    }

    # Agent 3 Schema: InnovationBatchLLM
    print("Testing Agent 3 schema (InnovationBatchLLM)...")
    t_start = time.perf_counter()
    a3_result = client.generate_json(
        "For candidate problem 'Grid peak load balancing during solar drop-off', classify opportunity and identify gap.",
        InnovationBatchLLM,
        "You are the Innovation Research Agent. Return schema-valid JSON only.",
    )
    t_a3 = time.perf_counter() - t_start
    print(f"  Agent 3 OK in {t_a3:.2f}s. Gaps evaluated: {len(a3_result.gaps)}")
    results["agent3"] = {"success": True, "time_s": round(t_a3, 2)}

    # Agent 4 Schema: SolutionLLM
    print("Testing Agent 4 schema (SolutionLLM)...")
    t_start = time.perf_counter()
    a4_result = client.generate_json(
        "Architect a buildable solution for grid battery coordination. Provide architecture, estimated hours, risks, and demo plan.",
        SolutionLLM,
        "You are the Solution Architect Agent. Return schema-valid JSON only.",
    )
    t_a4 = time.perf_counter() - t_start
    print(
        f"  Agent 4 OK in {t_a4:.2f}s. Solution title: {a4_result.title}, hours: {a4_result.estimated_hours}"
    )
    results["agent4"] = {"success": True, "time_s": round(t_a4, 2)}

    # Agent 5 Schema: CritiqueLLM
    print("Testing Agent 5 schema (CritiqueLLM)...")
    t_start = time.perf_counter()
    a5_result = client.generate_json(
        "Candidate: Community solar buffer controller. Feasibility: medium. Challenge this idea with 2 specific criticisms.",
        CritiqueLLM,
        "You are the Adversarial Critic Agent. Return schema-valid JSON only.",
    )
    t_a5 = time.perf_counter() - t_start
    print(
        f"  Agent 5 OK in {t_a5:.2f}s. Criticisms generated: {len(a5_result.criticisms)}"
    )
    results["agent5"] = {"success": True, "time_s": round(t_a5, 2)}

    gpu_final, _ = get_gpu_vram_mb()
    print(f"\nFinal Dedicated GPU VRAM: {gpu_final} MiB used / {gpu_total} MiB total")
    print("==================================================")
    print(" ALL 5 AGENT SCHEMAS VERIFIED ON SHARED MODEL!    ")
    print("==================================================")

    return {
        "success": True,
        "model": resolved_model,
        "gpu_vram_used_mb": gpu_final,
        "gpu_vram_total_mb": gpu_total,
        "smoke_tok_per_sec": round(smoke_tok_per_sec, 1),
        "results": results,
    }


if __name__ == "__main__":
    run_verification()
