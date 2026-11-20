"""Optional real-Ollama smoke test.

Run with:
    $env:RUN_OLLAMA_TESTS="1"; pytest tests/e2e/test_ollama_smoke.py -v
"""

from __future__ import annotations

import os

import pytest
from pydantic import BaseModel

from src.llm.client import OllamaClient


class SmokeAnswer(BaseModel):
    status: str
    confidence: int


@pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_TESTS") != "1",
    reason="Set RUN_OLLAMA_TESTS=1 to exercise the real local model",
)
def test_real_ollama_structured_output() -> None:
    client = OllamaClient()
    health = client.health()
    assert health["available"], health.get("error")
    assert health["models"], "No Ollama model installed"
    answer = client.generate_json(
        "Return JSON with status='ok' and confidence=1. Do not add anything else.",
        SmokeAnswer,
        "You return only schema-valid JSON.",
    )
    assert answer.status
    assert 0 <= answer.confidence <= 100
