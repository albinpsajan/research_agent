# Testing

HackathonIQ separates fast offline tests from optional live-network and
real-model tests. **Offline tests never call the network or Ollama.**

## Run the suite

```powershell
python -m pytest -q
```

Current verified result on Windows, Python 3.14.6:

```
39 passed, 1 skipped
```

The skipped test is the real-Ollama smoke test. It is skipped unless explicitly
enabled.

### Optional real-model smoke test

```powershell
$env:RUN_OLLAMA_TESTS="1"
python -m pytest tests/e2e/test_ollama_smoke.py -v
```

This checks that Ollama is reachable, at least one model is installed, and the
client can obtain schema-valid JSON from the real model.

## What the offline suite covers

| Area | Tests |
|---|---|
| Configuration | rubric weights total 100; invalid totals rejected |
| LLM robustness | JSON extraction from plain text, code fences, prose, arrays; malformed output rejection; truncation |
| Storage | budget warning, download guard, cache-only cleanup |
| Database | sessions, agent results, source dedupe, intelligence dedupe, refresh log, report round-trip |
| Evidence | SSRF/private URL rejection, public URL acceptance, hallucinated URL removal, similarity |
| Rubric | all gates pass, high score cannot hide a failed evidence gate, commonly-solved fails originality, unrealistic hours fail deadline |
| Full workflow | five-agent run selects one winner; run can reject all candidates; model failure marks session failed and preserves partial state |
| UI/CLI | every UI module imports; CLI `--help` works |

## Test doubles

`tests/fakes.py` provides:

- `FakeLLM` — schema-appropriate deterministic responses for every agent and
  rubric prompt; configurable score; `force_reject_all`.
- `FakeResearch` — deterministic search bundles, GitHub projects and pages.
- `FakeIntelligence` — empty Continuous Intelligence context.

The integration tests run the **real** LangGraph pipeline, real Pydantic
validation, real SQLite persistence and real report generation. Only the LLM
and outbound network calls are replaced.

## What is not covered offline

- Live connector behaviour against changing APIs (GitHub, arXiv, OpenAlex,
  Crossref, RSS, Wikipedia, Hacker News, DuckDuckGo).
- Real model latency and prompt adherence.
- Browser-level interaction beyond Streamlit's `AppTest` import/render checks.

These require live verification and are reported honestly in the final
acceptance walkthrough.

## Manual smoke checks

```powershell
# 1. Environment
python -m src.cli check

# 2. Database
python -m src.cli init-db

# 3. UI
python -m streamlit run ui/app.py
# open http://localhost:8501 and visit all five pages

# 4. A minimal real run (small bounds keep it tractable)
python -m src.cli research --theme "Sustainable cities" --max-domains 3 --problems-per-domain 1 --finalists 2 --debate-rounds 1 --no-ci

# 5. Continuous Intelligence
python -m src.cli intelligence-refresh
```

## Failure expectations

- If Ollama is offline, the UI shows an actionable error and `check` exits 1.
- If no model is installed, downloads are refused or explained; nothing is
  downloaded silently.
- If the model repeatedly returns invalid JSON, the run is marked `failed` with
  the stage and error persisted.
- If no candidate passes every gate, the run completes with
  `completed_no_winner`; this is a correct outcome, not a test failure.
