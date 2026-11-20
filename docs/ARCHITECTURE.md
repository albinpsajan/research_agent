# Architecture

HackathonIQ is a local-first Python application. It combines a LangGraph state
machine, five specialist agents, deterministic quality controls, a secure
research layer, SQLite persistence and a Streamlit interface.

```
Streamlit UI / CLI
        │
        ▼
HackathonPipeline (LangGraph StateGraph)
        │
        ├── prepare ─────────────── Continuous Intelligence context
        ├── hackathon_intelligence ─ Agent 1
        ├── domain_discovery ─────── Agent 2
        ├── innovation_research ──── Agent 3
        ├── solution_architecture ── Agent 4
        ├── adversarial_evaluation ─ Agent 5 + rubric/gates
        ├── report ───────────────── 24-section report generator
        └── finalize
        │
        ▼
Repository (SQLite) + data/ artefacts
```

## Design principles

1. **Evidence before generation.** Research is retrieved first; prompts contain
   numbered evidence; model-cited indices are validated; invented URLs are
   stripped.
2. **Deterministic controls over LLM judgement.** The seven mandatory gates are
   computed from data, not accepted from the model. The model may fail a gate,
   but it cannot waive one.
3. **Honest rejection.** The pipeline can finish with `completed_no_winner`.
   It never promotes an unqualified candidate to satisfy the user.
4. **Local-first.** One Ollama model, no paid APIs, no telemetry. Public HTTP
   sources are optional enrichment.
5. **Everything persisted.** Agent outputs, sources, domains, candidates,
   evaluations, debates and reports are stored with the session.
6. **Fail visibly.** A failed stage marks the session `failed`, stores the stage
   and error, preserves partial results and returns a clean error to the UI.

## Orchestration

`src/orchestration/pipeline.py` builds a LangGraph `StateGraph` over
`PipelineState` (a `TypedDict`). Each node returns a partial state update.
The graph is linear and bounded; `recursion_limit` is set to 30.

Progress is reported through an optional callback `(stage, message, fraction)`.
The Streamlit page uses it to update a progress bar and live log. Exceptions in
the callback are caught so a UI problem cannot corrupt a run.

Failure handling:

- `update_session_status(session_id, "failed")`
- store `orchestrator/pipeline_error` with stage, error type and message
- return a `PipelineResult` with `status="failed"` and partial artefacts

`src/orchestration/loader.py` reconstructs a `PipelineResult` from persisted
agent results and reports, so History can reopen a session without re-running it.

## Agents

All agents inherit `BaseAgent` (`src/agents/base.py`), which provides:

- shared LLM, research, repository and settings dependencies
- `_save()` for agent results
- `_source_urls()` for provenance
- evidence helpers (`evidence_lines`, `evidence_from_indices`)
- `sanitize_model_urls` and `similarity` guards

See [AGENTS.md](AGENTS.md) for each agent's contract.

## LLM layer

`src/llm/client.py` wraps Ollama's HTTP API:

- health, model list, model pull and model resolution
- JSON-schema generation from Pydantic models
- structured generation with tolerant JSON extraction, validation and bounded
  retry/repair
- fallback from the primary model to `qwen2.5:3b` when the primary is missing
- per-call usage statistics

No LangChain chat model is required at runtime; `langgraph` is used for
orchestration and the Ollama HTTP API is called directly for precise control.

## Research layer

`src/research/http_client.py` is the only outbound HTTP path used by connectors:

- URL validation and SSRF guard (public http/https only; no credentials,
  loopback, private ranges, link-local or file schemes)
- redirect re-validation
- robots.txt enforcement (configurable)
- per-host rate limiting
- bounded response size
- on-disk response cache with TTL
- HTML extraction with script/style/navigation removal and link collection

Connectors live in `src/research/`:

| Module | Sources |
|---|---|
| `github.py` | GitHub repository search and README excerpts |
| `scholarly.py` | arXiv, OpenAlex, Crossref |
| `web.py` | Wikipedia, Hacker News, DuckDuckGo HTML, RSS |
| `registry.py` | connector registry, `ResearchService`, source tracking |

`ResearchService` persists every retrieved source with session, URL, title,
type, reliability and retrieval time, deduplicated per session.

## Quality controls

`src/evaluation/rubric.py`:

1. Builds a scoring prompt from candidate, problem, gap, hackathon and
   organiser context.
2. Normalises model criterion names onto the eight weighted criteria.
3. Computes weighted scores out of 100.
4. Computes the seven deterministic gates from evidence counts, existing
   solutions, classification, implementation path, deadline, risk analysis and
   rule compliance.
5. Merges LLM gate justifications, but only lets the LLM *fail* a gate, never
   waive a deterministic failure.

The independent selector is guarded: it must choose a qualified finalist with a
score of at least 60; otherwise no winner is declared.

## Persistence

SQLite with append-only migrations (`src/database/migrations.py`). The schema
contains sessions, agent results, research sources, domain discoveries,
problem candidates, existing solutions, candidate solutions, evaluations,
debate history, final reports, intelligence items and refresh logs.

`DatabaseConnection` is thread-safe:

- `check_same_thread=False` because Streamlit reruns on different threads
- every operation serialized with an `RLock`
- WAL mode and a 5 s busy timeout
- explicit `transaction()` context manager

Migrations are applied idempotently at startup. Existing user data is never
dropped.

## Storage

`src/storage/manager.py` measures the application's own directories and the
free disk space. `check_before_download()` blocks a download that would exceed
the configured budget or leave insufficient disk. `cleanup_cache()` only walks
`data/cache` and never touches personal files.

## UI

`ui/app.py` is a single Streamlit entry point with sidebar navigation:

- **New research** — brief, controls, live progress, run
- **Results** — winner/rejection, scores, gates, domains, solutions, debate,
  evidence, report download
- **History** — persisted sessions and reports, reload into Results
- **Intelligence** — knowledge base, manual refresh, theme lookup, source config,
  refresh history
- **Settings** — model, download with storage guard, storage budget, safe
  cleanup, research defaults, privacy notes

`ui/components/common.py` owns the visual system, cached resources and shared
formatting. The SQLite connection is process-wide and thread-safe, so cached
Streamlit resources are safe across reruns.

## Configuration

`config/settings.py` loads, in increasing precedence:

1. built-in defaults
2. `data/user_settings.json` (written by Settings)
3. environment variables / `.env`

`EvaluationSettings` validates that weights total exactly 100. Invalid
configuration fails at startup rather than producing silently wrong scores.

## Known design limits

- The workflow is synchronous. Streamlit blocks during a run; the UI explains
  this. A future version could use a background worker.
- Public-source coverage varies. Some sites block crawlers; some APIs rate-limit.
- Local model quality determines prompt adherence. Schema validation and retries
  reduce, but do not eliminate, invalid output.
