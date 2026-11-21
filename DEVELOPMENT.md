# HackathonIQ — Developer Guide

Welcome to the HackathonIQ developer documentation. This document covers developer workflows, environment setup, testing, multi-track research architecture, database migrations, and extending the evaluation engine.

---

## 1. Quick Start

### Prerequisites
- **OS**: Windows 10/11
- **Python**: 3.11+ (Tested on Python 3.14.6)
- **Local LLM**: [Ollama for Windows](https://ollama.com/download/windows) with `qwen2.5:3b` or `qwen2.5:7b`
- **Target GPU**: NVIDIA RTX 3050 Laptop GPU (6 GB VRAM) / AMD Ryzen 5 or higher

### Environment Setup
```powershell
# Clone and navigate to repository
cd C:\Users\albin\Desktop\agent

# Install dependencies in editable mode
pip install -e .

# Verify Ollama service
ollama list
ollama run qwen2.5:3b "Hello"

# System verification check
python -m src.cli check
```

---

## 2. Running HackathonIQ

### Streamlit Interactive Web Application
```powershell
start.bat
# or directly via python:
python -m streamlit run ui/app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

### Command Line Interface (CLI)
```powershell
# Single-track research run
python -m src.cli research --theme "Sustainable Cities and Inclusive Urban Life" --name "CityHack"

# Fast testing run with constrained domains
python -m src.cli research --theme "Digital Health" --max-domains 4 --finalists 2

# Refresh Continuous Intelligence signals
python -m src.cli intelligence-refresh

# Generate/export a session report
python -m src.cli report --session-id <session_id> --out report.md
```

---

## 3. Multi-Track Hackathon Architecture

HackathonIQ natively supports competitions with arbitrary track counts (1, 2, 6, 8+ tracks) through `HackathonPipeline.run_multi_track()` and `CrossTrackComparisonEngine`.

### Key Developer Principles
1. **Shared vs. Independent Execution**:
   - `Agent 1` (Hackathon Intelligence) runs **once** across all tracks to formulate the shared organizer baseline (`shared_intelligence`).
   - `Agents 2–5` run **sequentially** for each track, ensuring domain specialization without memory spikes.
2. **Resource-Safe Garbage Collection**:
   - Always invoke `gc.collect()` between track turns to free GPU VRAM and Python heaps.
3. **Cross-Track Comparison Engine (`src/evaluation/cross_track_comparison.py`)**:
   - **Mode A (Best Overall Track)**: Cross-compares candidates across tracks under uniform standards to select the single best project, generating clear runner-up explanations.
   - **Mode B (Best Idea Per Track)**: Evaluates each track independently. Disqualified tracks strictly yield:
     `"No qualifying problem statement found for this track."`
   - **Duplicate Detection**: Computes token-based Jaccard similarity (threshold 0.58) and assigns candidates to their best-fit track based on track descriptions.

---

## 4. Database & Migrations

HackathonIQ uses SQLite (`data/hackathoniq.db`) with forward-only schema migrations:
- `Migration 001`: Initial schema (sessions, agent results, research sources, debates, evaluations, reports).
- `Migration 002`: Uniqueness and continuous intelligence indexes.
- `Migration 003`: Multi-track hackathon support (`hackathon_tracks`, `multi_track_comparisons`, and `sessions` table alterations).

To initialize or migrate the database programmatically:
```python
from src.database.connection import get_db
from src.database.migrations import initialize_database

db = get_db()
initialize_database(db)
```

---

## 5. Testing & Verification

HackathonIQ maintains a 100% passing automated test suite separating fast deterministic offline tests from live Ollama benchmarks.

### Running Automated Unit & Integration Tests
```powershell
# Run full offline test suite (109 passed, 2 skipped)
python -m pytest -q

# Run multi-track test suite specifically (17 scenarios)
python -m pytest tests/unit/test_multitrack.py -v

# Run 10 mandatory quality gate tests
python -m pytest tests/unit/test_ten_gates.py -v
```

### Running Live Ollama Benchmarks
```powershell
$env:RUN_OLLAMA_TESTS="1"
python -m pytest tests/e2e/test_ollama_smoke.py -v
python tests/benchmark_phase4_1_verification.py
```

---

## 6. Code Style & Pre-Commit Checklist

Before committing or pushing changes:
1. Ensure no API keys, tokens, `.env`, or database files are tracked by Git.
2. Run `python -m pytest -q` and verify all tests pass.
3. Verify that UI page imports succeed without errors:
   ```powershell
   python -c "import ui.pages.new_research; import ui.pages.results; import ui.pages.history; print('UI OK')"
   ```
4. Update `CHANGELOG.md` with relevant feature additions or architectural improvements.
