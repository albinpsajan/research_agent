# HACKATHONIQ — CHANGELOG
## Record of System Architecture, Intelligence Engineering, and Evaluation Improvements

---

## [Master Specification Implementation] — 2026-11-21

### Added:
- **Ten Mandatory Problem-Statement Evaluation Gates** (`src/evaluation/rubric.py`):
  - Upgraded from 7 to 10 official gates:
    1. Theme & Judging Alignment
    2. Real-World Problem Validation ($\ge 2$ independent sources)
    3. Kerala and India Relevance
    4. Existing-Solution Investigation
    5. Genuine Innovation and Differentiation
    6. Global-to-Local Adaptability
    7. Technical Feasibility and Data Availability
    8. Economic and Practical Viability
    9. Hackathon Buildability and Demonstration ($\le 1.15 \times \text{hours}$, demo plan)
    10. Risk, Ethics and Sustainability
- **General Theme Mode 90/100 Scoring Rubric**:
  - Automatically activates when no specific organizer or sponsors are provided.
  - Marks Organizer & Sponsor Alignment as **NOT ASSESSABLE** (0.0 raw score).
  - Normalizes the remaining 7 assessable criteria (/90) to the standard 100-point scale: $\text{Normalized} = (\text{Raw} / 90) \times 100$.
- **Hackathon Playbook Knowledge Base Subsystem** (`src/knowledge/hackathon_playbook/`):
  - Created embedded SQLite database with FTS5 search index (`playbook_fts`).
  - Ingested 28 curated seed entries from Devpost, MLH, YouTube retrospectives, Bread04 guide, and Microsoft Agent Academy.
  - Added `HackathonPlaybookService` with targeted retrieval methods for each of the 5 agents.
- **Kerala & India Official Source Registry** (`src/research/sources/kerala_india_registry.py`):
  - Registered 14 official government repositories, research institutes, and satellite portals (Kerala Data Portal, DES ODR, KAU Agromet, KSDMA, SAPCC, data.gov.in, ICAR, IMD, ISRO, NITI Aayog, FAOSTAT, World Bank, Copernicus, NASA).
  - Automated domain matching and query generator directed at official government domains.
- **5-Tier Global-to-Local Adaptability Models** (`src/models/research.py`):
  - Added `AdaptabilityClassification` enum (Tiers A through E).
  - Added `GlobalToLocalAdaptation` model for explicit transferability mapping.
- **Comprehensive Unit Test Suites**:
  - `tests/unit/test_ten_gates.py` (13 tests verifying all 10 gates and General Theme Mode).
  - `tests/unit/test_playbook.py` (4 tests verifying Playbook FTS5 and agent retrieval).
  - `tests/unit/test_kerala_india_sources.py` (6 tests verifying source catalog and adaptation).
- **Authoritative Documentation Suite**:
  - `docs/CHECKLIST.md` (Master implementation checklist).
  - `docs/SOURCE_REGISTRY.md` (Catalog of official portals).
  - `docs/AGENT_RESPONSIBILITIES.md` (Detailed agent specifications).
  - `docs/HACKATHON_PLAYBOOK.md` (Playbook architecture & seed lessons).
  - `docs/EVALUATION_FRAMEWORK.md` (Ten gates, 100-pt rubric, debate mechanics).
  - Updated `docs/ARCHITECTURE.md` and `docs/TESTING.md`.

---

## [Phase 4.1 — Final Winner Verification and Scientific Validation] — 2026-11-20

### Added:
- Verified requirement provenance distinguishing user constraints, official hackathon rules, and solution design choices.
- In General Theme Mode, enforced that Organizer Alignment is not assessable and must not receive an invented score.
- Defended the scientific validity of agroforestry ML via a **Two-Tier Hybrid Architecture**:
  - Tier 1: Deterministic Multi-Criteria Decision Analysis (AHP) on biophysical envelope envelopes.
  - Tier 2: Statistical Ecological Niche Modeling (MaxEnt / Random Forest) on >15,000 real GBIF presence points.
- Produced `docs/PHASE4_1_FINAL_VERIFICATION_REPORT.md` validating Candidate Beta with 77.25/90 raw, 85.83/100 normalized score.

---

## [Phase 4 — Independent Winner Audit and Intelligence QA] — 2026-11-20

### Fixed:
- Overturned flawed Phase 3 winner (Candidate C01 - Satellite Air Quality) due to theme drift, citation mismatches, and spatial resolution limits (3.5 km vs 1 ha farm).
- Crowned **Candidate C02 ("AI-Driven Agroforestry for Climate-Resilient Agriculture in Dryland Savanna Zones")** with 91.50/100 score.
- Completed RAM memory optimizations across `pipeline.py`, `http_client.py`, and `registry.py`, reducing memory footprint by 79.4% (+234.3 MB delta vs +1,137.1 MB baseline).
- Added robust trailing-comma repair in `src/llm/client.py`.
- Produced `docs/PHASE4_WINNER_AUDIT_REPORT.md` and `data/reports/R-phase4-audit.md`.

---

## [Phase 3 — Intelligence Engineering and Research Quality Improvement] — 2026-11-20

### Added:
- Removed artificial domain limit (`max_domains=3`) in favor of dynamic discovery bounded by budget and diminishing-returns stopping reasons.
- Implemented `EvidenceAggregator` with candidate-specific evidence association, keyword relevance scoring, and failure categorization.
- Enhanced existing solution research with GitHub query optimization and competitive comparison.
- Added strict constraint provenance tracking (`CategorizedConstraint`).
- Produced `docs/PHASE3_REPORT.md` and `data/reports/R-a388fd9e.md`.

---

## [Phase 2 — Real-World Intelligence & Quality Validation] — 2026-11-20

### Added:
- First end-to-end evaluation using local `qwen2.5:3b` model on theme "Artificial Intelligence for Climate-Resilient Agriculture and Rural Communities".
- Performed initial security audit verifying zero secrets in Git history.
- Produced `data/reports/R-4a0e2ced.md`.

---

## [Phase 1 — Initial Implementation & Local AI Integration] — 2026-11-20

### Added:
- Initial project scaffold with LangGraph state machine and five specialist agents.
- Local Ollama client integration for `qwen2.5:3b` on NVIDIA RTX 3050 Laptop GPU.
- 100-point rubric with 7 initial mandatory quality gates.
- SQLite persistence and Streamlit UI.
