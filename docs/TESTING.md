# HACKATHONIQ — TESTING AND VERIFICATION STRATEGY
## Fast Deterministic Test Suites, Live Benchmarking, and Quality Gate Validation

HackathonIQ enforces an exhaustive test suite separating offline deterministic unit and integration tests from live model verification benchmarks.

---

## 1. Test Suite Overview & Execution

To run the complete automated test suite:

```powershell
python -m pytest tests/ -v
```

### Current Test Suite Metrics (Verified):
- **Total Tests**: 111
- **Passed**: 109
- **Skipped**: 2 (Real Ollama smoke tests, skipped when offline)
- **Execution Time**: ~26 seconds
- **Pass Rate**: 100%

---

## 2. Test Suite Breakdown by Layer

| Test Module | Test Focus & Scope | Count | Status |
| :--- | :--- | :---: | :---: |
| `tests/unit/test_multitrack.py` | Multi-track hackathon intelligence: 17 exhaustive verification scenarios across Modes A & B, dynamic tracks (1, 2, 6, 8+), cross-track comparison, duplicate detection, fault recovery, and backward compatibility | 17 | `PASSED` |
| `tests/unit/test_ten_gates.py` | Validates all 10 Mandatory Quality Gates, pass/fail scenarios, and General Theme Mode raw/normalized scoring | 13 | `PASSED` |
| `tests/unit/test_playbook.py` | Schema validation, SQLite FTS5 search, seed data ingestion, agent-tailored retrieval, prompt formatting | 4 | `PASSED` |
| `tests/unit/test_kerala_india_sources.py` | Catalog coverage (Kerala/India/Global), domain matching, targeted queries, 5-tier transferability taxonomy | 6 | `PASSED` |
| `tests/unit/test_rubric.py` | Core rubric weighting, 100-point total constraint, gate veto mechanisms, General Theme Mode 90/100 normalization | 4 | `PASSED` |
| `tests/unit/test_phase3_regression.py` | Dynamic domain discovery, stopping reasons, evidence aggregation, gate failure categorization, GitHub query optimizer | 9 | `PASSED` |
| `tests/unit/test_evidence.py` | SSRF/private IP rejection, DNS rebinding guards, URL sanitization, similarity clustering, finalist label extraction | 13 | `PASSED` |
| `tests/unit/test_llm_json.py` | Robust JSON parsing: plain objects, markdown code fences, prose extraction, nested brackets, trailing comma repair | 6 | `PASSED` |
| `tests/unit/test_repository.py` | SQLite session persistence, agent result storage, source deduplication, track & multi-track comparison persistence | 5 | `PASSED` |
| `tests/unit/test_storage.py` | 30 GB budget warnings, download guards blocking disk overrun, cache-only pruning safety | 3 | `PASSED` |
| `tests/unit/test_config.py` | Rubric weight totals, invalid configuration rejection | 2 | `PASSED` |
| `tests/unit/test_intelligence.py` | Continuous intelligence caching, source failure marking, honest theme lookup | 3 | `PASSED` |
| `tests/integration/test_pipeline.py` | Full multi-agent workflow: single winner selection, honest rejection of all candidates, graceful error recovery | 3 | `PASSED` |
| `tests/e2e/test_ui_imports.py` | Streamlit UI pages import, CLI `--help` verification | 2 | `PASSED` |
| `tests/e2e/test_ollama_smoke.py` | Live inference smoke test with local Ollama service | 1 | `OPTIONAL` |

---

## 3. Running Live Ollama & Quality Verification Benchmarks

### 1. Local Model Smoke Test
To verify the active local Ollama service with `qwen2.5:3b`:
```powershell
$env:RUN_OLLAMA_TESTS="1"
python -m pytest tests/e2e/test_ollama_smoke.py -v
```

### 2. Live Winner Verification Benchmark
To run the live scientific verification benchmark against local Ollama:
```powershell
python tests/benchmark_phase4_1_verification.py
```
This benchmark evaluates real model responses against the 10 mandatory quality gates, records latency, token throughput, and GPU VRAM offload.

---

## 4. Test Doubles & Deterministic Fakes (`tests/fakes.py`)

Deterministic test execution is enabled by `tests/fakes.py`:
- **`FakeLLM`**: Generates schema-conformant Pydantic outputs for every agent and evaluation prompt; allows testing score adjustments and rejection triggers deterministically.
- **`FakeResearch`**: Returns fixed search bundles, GitHub repositories, and web excerpts without network I/O.
- **`FakeIntelligence`**: Ingests controlled intelligence contexts for isolated agent testing.

The integration tests run the **real** LangGraph pipeline, real Pydantic validation, real SQLite persistence, and real report generation. Only external LLM and network calls are mocked.
