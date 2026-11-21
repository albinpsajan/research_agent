"""Real local AI sequential multi-theme benchmark using local Qwen 2.5 3B.

Executes sequentially across 3 distinct research themes:
- Theme 1: Climate-Resilient Agriculture & Rural Communities
- Theme 2: Healthcare & Dengue Outbreak Surveillance
- Theme 3: Vernacular Education & Civic Grievance Redressal

Run explicitly with:
    $env:RUN_OLLAMA_TESTS="1"; python -m pytest tests/e2e/test_live_three_themes.py -v -s
"""

from __future__ import annotations

import gc
import os
import time
from typing import Any

import pytest
from pydantic import BaseModel, Field

from src.llm.client import OllamaClient


class LiveDeconstructedTheme(BaseModel):
    """Structured response from Agent 1 theme deconstruction."""

    theme_summary: str = Field(description="Summary of core theme intent")
    primary_domain: str = Field(description="Primary technical/scientific domain")
    key_subdomains: list[str] = Field(default_factory=list, description="Relevant subdomains")
    target_beneficiaries: list[str] = Field(default_factory=list, description="Target end-users")
    high_stakes_consequences: str = Field(description="Why this problem matters economically/socially")


BENCHMARK_THEMES = [
    {
        "id": "THEME-01",
        "name": "Agriculture & Climate",
        "theme": "Artificial Intelligence for Climate-Resilient Agriculture and Rural Communities",
    },
    {
        "id": "THEME-02",
        "name": "Healthcare & Surveillance",
        "theme": "AI for Rural Telemedicine and Dengue Outbreak Surveillance in Monsoonal Belts",
    },
    {
        "id": "THEME-03",
        "name": "Vernacular & Civic Governance",
        "theme": "Vernacular Language AI for Public Grievance Redressal and Grassroots Literacy",
    },
]


@pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_TESTS") != "1",
    reason="Live Ollama tests require RUN_OLLAMA_TESTS=1 environment variable.",
)
def test_sequential_three_themes_with_real_ollama():
    """Verify that local Ollama Qwen 2.5 3B handles 3 consecutive themes reliably."""
    client = OllamaClient()
    health = client.health()
    assert health["available"], f"Ollama not available: {health.get('error')}"
    assert "qwen2.5:3b" in health["models"], f"qwen2.5:3b not installed. Found: {health['models']}"

    benchmark_results: list[dict[str, Any]] = []

    print("\n" + "=" * 70)
    print("STARTING LIVE OLLAMA SEQUENTIAL 3-THEME BENCHMARK (qwen2.5:3b)")
    print("=" * 70)

    for item in BENCHMARK_THEMES:
        theme_id = item["id"]
        theme_name = item["name"]
        theme_text = item["theme"]

        print(f"\n[RUNNING] {theme_id} - {theme_name}")
        print(f"Theme prompt: '{theme_text}'")

        system_prompt = (
            "You are an expert autonomous hackathon intelligence researcher. "
            "Deconstruct the hackathon theme into its foundational intent, domains, and impact metrics. "
            "Return strictly valid JSON conforming to the schema."
        )

        user_prompt = (
            f"Hackathon Theme: {theme_text}\n\n"
            "Analyze this theme. Extract:\n"
            "1. theme_summary\n"
            "2. primary_domain\n"
            "3. key_subdomains (at least 2)\n"
            "4. target_beneficiaries (at least 2)\n"
            "5. high_stakes_consequences"
        )

        # Force garbage collection between sequential iterations to prevent memory accumulation
        gc.collect()

        start_time = time.perf_counter()
        response: LiveDeconstructedTheme = client.generate_json(
            user_prompt,
            LiveDeconstructedTheme,
            system_prompt,
        )
        elapsed_sec = round(time.perf_counter() - start_time, 2)

        print(f"[COMPLETED in {elapsed_sec}s]")
        print(f"  Primary domain: {response.primary_domain}")
        print(f"  Key subdomains: {response.key_subdomains}")
        print(f"  Beneficiaries: {response.target_beneficiaries}")

        # Assert real structural validity
        assert len(response.theme_summary) > 10, "Summary too short"
        assert len(response.primary_domain) > 2, "Primary domain missing"
        assert len(response.key_subdomains) >= 1, "Subdomains missing"
        assert len(response.target_beneficiaries) >= 1, "Beneficiaries missing"

        benchmark_results.append({
            "theme_id": theme_id,
            "theme_name": theme_name,
            "latency_sec": elapsed_sec,
            "primary_domain": response.primary_domain,
            "subdomain_count": len(response.key_subdomains),
            "status": "passed",
        })

    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY (ALL 3 THEMES EXECUTED SEQUENTIALLY):")
    for res in benchmark_results:
        print(f"- {res['theme_id']} ({res['theme_name']}): {res['latency_sec']}s | Primary: {res['primary_domain']}")
    print("=" * 70)

    assert len(benchmark_results) == 3
    assert all(r["status"] == "passed" for r in benchmark_results)
