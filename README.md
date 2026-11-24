# HackathonIQ

**Evidence over ideas.** A locally runnable, five-agent hackathon intelligence system for Windows.
It researches a hackathon, discovers domains dynamically, investigates what already exists,
architects buildable solutions, attacks them in bounded debate, and selects **one** defensible
problem statement — or honestly rejects every candidate.

No paid AI API is required. All inference runs through one shared local Ollama model.

---

## What it does

| Stage | Agent | Output |
|---|---|---|
| 1 | Hackathon Intelligence | Organiser mission/ideology, prior editions, judges, sponsors, criteria, rules, deadlines |
| 2 | Dynamic Domain & Problem Discovery | Domains generated from the theme and organiser evidence (no fixed industry list), with grounded problem candidates |
| 3 | Global Innovation & Existing-Solution Research | Real GitHub projects, papers (arXiv/OpenAlex/Crossref), products, news; honest opportunity classification |
| 4 | Solution Architect & Feasibility | Cross-domain finalists, architecture, data/API needs, risks, hour estimates |
| 5 | Adversarial Critic & Final Evaluator | Bounded evidence-backed debate, 100-point rubric, ten mandatory gates, independent selection or honest rejection |

The final artefact is a persisted 24-section Markdown report with provenance, freshness,
debate transcript, scoring breakdown, gate outcomes and a downloadable JSON result.

---

## Requirements

- Windows 10/11
- Python 3.11+ (tested on Python 3.14.6)
- [Ollama for Windows](https://ollama.com/download/windows)
- One local model. Recommended for a 6 GB RTX 3050: `qwen2.5:7b` (~4.7 GB, 4-bit).
  Lighter fallback: `qwen2.5:3b` (~2 GB).
- 16 GB RAM recommended.
- Disk: the default **30 GB budget is a guard-rail, not an allocation**. HackathonIQ
  warns before a download would exceed it and never deletes personal files.

## Install

```powershell
# 1. Python dependencies (from the project directory)
pip install -e .

# 2. Ollama (if not already installed)
winget install --id Ollama.Ollama --exact

# 3. Pull the local model
ollama pull qwen2.5:7b

# 4. Check everything
python -m src.cli check
```

Optional: copy `.env.example` to `.env` and set `GITHUB_TOKEN` to raise GitHub's
unauthenticated rate limit. No token is required.

## Run

```powershell
start.bat
# or
python -m streamlit run ui/app.py
```

Open <http://localhost:8501>. The sidebar shows model, Ollama and storage status.

### CLI

```powershell
python -m src.cli check
python -m src.cli research --theme "Sustainable cities and inclusive urban life" --name "CityHack"
python -m src.cli research --theme "Digital health" --max-domains 6 --finalists 4 --no-ci
python -m src.cli intelligence-refresh
python -m src.cli scheduler --tick 300
python -m src.cli report --session-id <id> --out report.md
```

A full run typically takes 10–40 minutes on a 6 GB RTX 3050 depending on domain
count, model speed and network conditions. Research quality is prioritised over speed.

---

## User Interface — Minimal Two-Page Experience

HackathonIQ features a streamlined ChatGPT-style research workspace designed around two core views:

1. **New Research**:
   - **Option A Guided Workflow**: Ingests hackathon PDFs, images, and rulebooks to auto-extract parameters, while keeping full user control (research launches **only** upon explicit user confirmation).
   - **Manual Parameter Builder**: Allows defining single- or multi-track challenges manually with configurable geographical priority (Kerala, India National, Global).
   - **Pre-Flight Duplicate Detection**: Detects matching past research runs and offers instant result loading or clean re-runs.
   - **Live Deliberation Progress**: Transparent 5-stage pipeline indicator replacing raw developer logs.
   - **Embedded Results Workspace**: Seamlessly explores winning solution blueprints, cross-track comparisons, quality gate audits, and grounded evidence citations.

2. **History**:
   - **Single-Topic Archive**: One clean card per research session displaying hackathon theme, track count, mode, and execution status.
   - **Search & Filtering**: Search across past hackathons and filter by completion status and track mode.
   - **Direct Actions**: Instant result inspection (`[Load Results →]`), markdown report exports (`[📄 Download Report]`), and safe cascading deletion (`[🗑 Delete]`).

---

## Two modes + Multi-Track Research

### A. Hackathon Research Mode (Single & Multi-Track)
A deep, five-agent workflow for a specific hackathon. Reuses stored Continuous
Intelligence signals when enabled, but never requires them.
- **Single-Track Mode**: Researches the central theme from organizer expectations to a single winning problem statement.
- **Multi-Track Mode**: Evaluates an arbitrary number of tracks (1, 2, 6, 8+ tracks):
  - **Shared Organizer Research**: Agent 1 runs once across all tracks to establish common criteria.
  - **Sequential Track Pipeline**: Agents 2–5 research each track independently in sequential order, preserving GPU VRAM (RTX 3050 6GB) via `gc.collect()`.
  - **Mode A (Best Overall Track)**: Selects the single strongest idea across all tracks with runner-up explanations.
  - **Mode B (Best Idea Per Track)**: Crowns the top idea for every track independently; for disqualified tracks, reports: *"No qualifying problem statement found for this track."*
  - **Cross-Track Comparison Engine**: Employs token Jaccard similarity (0.58) to identify cross-track duplicates and assign best-fit tracks.

### B. Continuous Global Intelligence Mode
A local, provenance-tracked knowledge base refreshed manually or on a schedule:

- GitHub recent repositories, arXiv, OpenAlex, RSS and Hacker News collectors.
- Configurable interval (`CI_REFRESH_INTERVAL_HOURS`, default 24 h).
- Deduplication by URL, freshness dates, stale flags, per-source refresh logs.
- Scheduler performs **no network work** when the interval has not elapsed.
- Watch topics live in `config/intelligence_sources.json` and are user-editable.
  They drive background collection only; they never constrain dynamic domain discovery.

---

## Quality controls & Ten Mandatory Gates

**100-point rubric** (weights must total 100, validated at startup):
problem significance 15 · originality 15 · technical feasibility 15 · theme relevance 15 ·
organiser/sponsor alignment 10 · innovation 10 · implementation within deadline 10 ·
demonstration appeal 10. In General Theme Mode, Organizer Alignment (10 pts) is unassessable and scores are normalized to 100.

**Ten mandatory quality gates** (deterministic checks, not LLM discretion):

1. Theme and Judging Alignment
2. Real-World Problem Validation ($\ge 2$ independent sources, credibility $\ge 0.60$)
3. Kerala and India Relevance (14 official portals, district-level specificity)
4. Existing-Solution Investigation (GitHub repositories & arXiv papers)
5. Genuine Innovation and Differentiation ($\ge 30$ characters unique differentiation)
6. Global-to-Local Adaptability (5-tier transferability taxonomy: Tiers A through E)
7. Technical Feasibility and Data Availability (zero unavailable dependencies)
8. Economic and Practical Viability (zero mandatory paid cloud AI APIs)
9. Hackathon Buildability and Demonstration ($\le 1.15 \times \text{deadline}$, 3-minute hero flow)
10. Risk, Ethics and Sustainability ($\ge 2$ risks, $\ge 1$ disadvantage, $\ge 1$ mitigation)

A high rubric score **cannot** conceal a failed gate. A candidate with any failed gate is
disqualified. If no candidate qualifies, no winner is declared and the report explains why.
The independent selector must choose a qualified candidate with ≥ 60/100; otherwise the
run is recorded as `completed_no_winner`.

**Evidence integrity.** Model output is schema-validated. Invented URLs are removed
against retrieved evidence. Existing solutions must cite valid retrieved-evidence indices.
Unsupported claims are logged, not hidden.

---

## Data and privacy

Everything stays under `data/`:

```
data/
  hackathoniq.db      SQLite database (sessions, agents, sources, debates, reports)
  cache/              HTTP cache (safe to clean)
  reports/            Markdown reports
  logs/               Application logs
  user_settings.json  UI-managed overrides
```

Research requests go directly to public APIs/websites. All inference is local.
The app sends no prompts or findings to a paid AI service.

The storage cleanup action only removes files inside `data/cache` older than the
chosen age. It never touches models, reports, the database, or personal files.

---

## Project layout

```
config/            validated settings, logging, CI source config
src/agents/        the five specialist agents + shared evidence guards
src/evaluation/    100-point rubric and seven deterministic gates
src/research/      secure HTTP client, GitHub, arXiv, OpenAlex, Crossref, RSS, Wikipedia, HN, web search
src/llm/           Ollama structured-output client with retry/repair
src/orchestration/ LangGraph state machine and session loader
src/intelligence/  Continuous Global Intelligence service and scheduler
src/reports/       24-section report generator
src/database/      SQLite schema, append-only migrations, repository
src/storage/       storage budget, warnings, safe cache cleanup
ui/                Streamlit application
tests/             unit, integration and optional real-model tests
docs/              architecture, agents, testing, sources, checklist
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/AGENTS.md](docs/AGENTS.md),
[docs/TESTING.md](docs/TESTING.md), [docs/SOURCES_AND_LIMITS.md](docs/SOURCES_AND_LIMITS.md)
and [docs/IMPLEMENTATION_CHECKLIST.md](docs/IMPLEMENTATION_CHECKLIST.md).

---

## Honest limitations

- Quality depends on the local model and on public-source availability. Weak models may
  fail schema validation repeatedly; the run is marked failed rather than faked.
- GitHub's unauthenticated API is rate-limited; a token is optional but recommended.
- Some sites block crawlers or require JavaScript. Failures are recorded per source.
- The system does not guarantee a winning idea. It is allowed to reject everything.
- A 6 GB GPU may need `qwen2.5:3b` and longer timeouts for reliable structured output.

## Testing

```powershell
python -m pytest -q
# optional real-model smoke test
$env:RUN_OLLAMA_TESTS="1"; python -m pytest tests/e2e/test_ollama_smoke.py -v
```

Offline tests use deterministic fake models and connectors; they never call the network.
