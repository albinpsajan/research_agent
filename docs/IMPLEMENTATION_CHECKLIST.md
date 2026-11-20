# Implementation checklist

Status is honest: `[x]` verified, `[~]` implemented but not yet verified live,
`[ ]` outstanding.

## Foundation

- [x] Python project metadata and dependency declaration (`pyproject.toml`)
- [x] Validated central configuration with defaults, user overrides and env precedence
- [x] Rubric weights validated to total exactly 100
- [x] Logging configuration and log file under `data/logs`
- [x] Pydantic models for hackathon, domain, research, candidate, evaluation, report, intelligence and pipeline
- [x] SQLite connection with WAL, foreign keys, busy timeout and thread-safe access
- [x] Append-only migrations 001 and 002
- [x] Repository methods for sessions, agent results, sources, domains, problems, solutions, evaluations, debates, reports and intelligence
- [x] Storage manager with budget, warnings, download guard and safe cache cleanup

## LLM

- [x] Ollama health and model listing
- [x] Model pull with storage check
- [x] Primary/fallback model resolution
- [x] JSON schema generation from Pydantic models
- [x] Tolerant JSON extraction
- [x] Schema validation, retry and repair
- [x] Usage statistics
- [~] Real structured-output smoke test against a running Ollama model

## Research

- [x] SSRF-safe HTTP client with redirect validation
- [x] robots.txt enforcement, per-host rate limit, bounded response size, TTL cache
- [x] GitHub connector
- [x] arXiv, OpenAlex, Crossref connectors
- [x] Wikipedia, Hacker News, DuckDuckGo, RSS connectors
- [x] Connector registry and `ResearchService`
- [x] Per-session source tracking with dedupe
- [x] Live connector verification against current public APIs

## Agents

- [x] Agent 1 — Hackathon Intelligence
- [x] Agent 2 — Dynamic Domain and Problem Discovery (no fixed domain list)
- [x] Agent 3 — Global Innovation and Existing-Solution Research
- [x] Agent 4 — Solution Architect and Feasibility
- [x] Agent 5 — Adversarial Critic and Final Evaluator
- [x] Evidence-index validation and hallucinated-URL removal
- [x] Bounded debate with justified score adjustment
- [x] Independent selection with qualification guard and honest rejection

## Evaluation

- [x] 100-point weighted rubric
- [x] Seven deterministic mandatory gates
- [x] High score cannot conceal a failed gate
- [x] Minimum 60/100 for a winner
- [x] Score adjustment bounds and unresolved-criticism guard

## Orchestration and output

- [x] LangGraph state and five-agent pipeline
- [x] Continuous Intelligence context injection
- [x] Progress callback and live stage log
- [x] Failure handling with session status, stage and partial artefacts
- [x] Session loader for History
- [x] 24-section report generator
- [x] Report persisted as JSON and Markdown

## Continuous Global Intelligence

- [x] Configurable watch topics and collectors
- [x] Manual refresh
- [x] Interval-aware scheduler with no work when not due
- [x] Dedupe by URL, freshness dates, stale flags
- [x] Refresh logs and source errors
- [x] Live scheduled refresh over a real interval

## Interface

- [x] Streamlit app with five pages and shared visual system
- [x] New research form with bounds and live progress
- [x] Results page with winner/rejection, scoring, gates, domains, solutions, debate, evidence and downloads
- [x] History page with persisted sessions and report download
- [x] Intelligence page with knowledge base, manual refresh, theme lookup and config
- [x] Settings page with model download guard, storage budget, safe cleanup and research defaults
- [x] CLI: `check`, `init-db`, `pull-model`, `research`, `intelligence-refresh`, `scheduler`, `report`
- [x] `start.bat`

## Tests

- [x] Offline unit tests
- [x] Offline integration test of the full pipeline
- [x] Honest-rejection integration test
- [x] Failure-preservation integration test
- [x] UI module and CLI smoke tests
- [x] `pytest` result: 39 passed, 1 skipped
- [ ] Real-model end-to-end run
- [ ] Live UI walkthrough with a real run

## Documentation

- [x] README
- [x] Architecture
- [x] Agents
- [x] Testing
- [x] Sources and limits
- [x] Implementation checklist
- [x] `.env.example`

## Final acceptance

- [ ] Ollama installed and running on the target machine
- [ ] Recommended model pulled after storage check
- [ ] All five agents exercised with the real model
- [ ] Dynamic domains observed in a real run
- [ ] Sources and provenance visible in the report
- [ ] Candidates compared and debated in a real run
- [ ] Winner selected or all candidates honestly rejected in a real run
- [ ] Continuous Intelligence refreshed and reused
- [ ] Persistence verified across an app restart
- [ ] Reports downloadable from UI and CLI
- [ ] Final honest test and limitation report delivered
