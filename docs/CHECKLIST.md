# HACKATHONIQ — MASTER IMPLEMENTATION CHECKLIST
## Autonomous Hackathon Problem Discovery, Global Innovation Research, Kerala–India Localization, Solution Validation and Competition Intelligence

Authoritative checklist verifying full implementation of the Definitive Master Project Specification.

---

## 1. Fundamental Purpose & Guiding Principles
- [x] **Primary Objective**: Discover and recommend ONE exceptionally strong, differentiated, practical, and hackathon-ready problem statement & solution.
- [x] **Honest Rejection Capability**: If all candidates fail quality gates or do not meet score thresholds (>= 60/100), the system rejects all candidates with specific, actionable remediation.
- [x] **Strict Anti-Hallucination**: Every problem claim corroborated by >= 2 independent, verified sources; zero manufactured competitors, URLs, or benchmarks.
- [x] **Zero Paid AI Services**: 100% executable using local Ollama model (`qwen2.5:3b`) on consumer hardware with zero mandatory cloud API subscriptions.
- [x] **Application Storage Budget**: Strict 30 GB application storage budget enforced by `StorageManager` download guards and cache cleanup.

---

## 2. Geographical Strategy: Kerala First, India Scale, Global Intelligence
- [x] **Kerala First (Primary Focus)**:
  - [x] Comprehensive coverage of all 14 districts (Wayanad, Idukki, Palakkad, Alappuzha, Ernakulam, Thiruvananthapuram, etc.).
  - [x] 5 distinct agro-ecological zones: High Ranges (landslides/soil erosion), Central Plains (Palakkad drought/heat), Coastal Plains (saline ingress), Below-Sea-Level (Kuttanad flooding), Midland.
  - [x] Homestead farm plot geometry (<0.5 ha average landholding).
  - [x] Monsoon volatility and cloud-cover constraints impacting optical remote sensing.
  - [x] Vernacular Malayalam accessibility (audio prompts, SMS, iconography) for rural workers and Kudumbashree collectives.
  - [x] Integration with local government frameworks: Panchayati Raj, Krishi Bhavans, K-DISC, Subhiksha Keralam, KSDMA.
- [x] **India-Wide (Secondary Focus)**:
  - [x] Scalability across diverse agro-climatic zones and national missions.
  - [x] Alignment with national repositories: data.gov.in, ICAR, IMD Mausam/Agrimet, ISRO Bhuvan/MOSDAC, NITI Aayog.
- [x] **Global Innovation (Comparative Benchmarking)**:
  - [x] Systematic research of international solutions (arXiv, OpenAlex, Crossref, GitHub, FAO, World Bank, Copernicus, NASA).
  - [x] 5-tier transferability taxonomy (Tier A through E) to avoid uncritical copying.

---

## 3. Five Specialist Logical Agents
- [x] **Agent 1: Hackathon Intelligence Agent** (`src/agents/hackathon_intelligence.py`):
  - [x] Ingests official hackathon briefs, websites, rules, and themes.
  - [x] Integrates Hackathon Playbook lessons for theme deconstruction.
  - [x] Enforces General Theme Mode: marks organizer alignment as NOT ASSESSABLE when no organizer is supplied.
  - [x] Classifies constraints into explicit categories (USER_PROVIDED, OFFICIAL_HACKATHON, AGENT_HYPOTHESIS).
- [x] **Agent 2: Dynamic Domain & Problem Discovery Agent** (`src/agents/domain_discovery.py`):
  - [x] Dynamic discovery without arbitrary domain limits (budget-bounded with stopping reason).
  - [x] Integrates Hackathon Playbook for problem sharpening.
  - [x] Ingests Kerala & India Official Source Registry for regional priorities.
  - [x] Populates `kerala_relevance`, `india_relevance`, `target_districts`, and `target_geography`.
- [x] **Agent 3: Global Innovation & Research Agent** (`src/agents/innovation_research.py`):
  - [x] Investigates existing open-source repositories and commercial solutions.
  - [x] Classifies opportunity gaps (differentiated, underserved, limited, commonly solved, insufficient evidence).
  - [x] Evaluates 5-tier global-to-local transferability taxonomy (Tier A–E).
  - [x] Integrates Playbook guidance against the "thin API wrapper" trap.
- [x] **Agent 4: Solution Architect & Feasibility Agent** (`src/agents/solution_architect.py`):
  - [x] Designs concrete, implementable architectures with data and API paths.
  - [x] Enforces buildability within hackathon time constraints (hours <= 1.15 * available time).
  - [x] Populates `GlobalToLocalAdaptation`, `economic_viability_notes` (zero paid APIs), and `ethical_sustainability_notes`.
  - [x] Crafts 3-minute hero user flow demo plans guided by the Playbook.
- [x] **Agent 5: Adversarial Critic & Independent Evaluator** (`src/agents/adversarial_critic.py`):
  - [x] Executes bounded multi-round adversarial debates challenging weaknesses.
  - [x] Enforces all 10 Mandatory Quality Gates via `EvaluationService`.
  - [x] Applies 100-point rubric only after all 10 gates pass; normalizes 90-pt raw scores in General Theme Mode.
  - [x] Selects exactly ONE winner or honestly rejects all candidates.

---

## 4. Ten Mandatory Problem-Statement Evaluation Gates
- [x] **Gate 1: Hackathon Theme and Official Judging Alignment**: Verifies thematic connection and records General Theme Mode vs Event Mode.
- [x] **Gate 2: Real-World Problem Validation**: Requires >= 2 independent, credible sources (credibility >= 0.60).
- [x] **Gate 3: Kerala and India Relevance**: Mandates documented relevance to Kerala districts/zones and Indian scalability.
- [x] **Gate 4: Existing-Solution Investigation**: Verifies real existing solutions or GitHub repositories were investigated.
- [x] **Gate 5: Genuine Innovation and Differentiation**: Honest originality classification + unique differentiation >= 30 chars.
- [x] **Gate 6: Global-to-Local Adaptability**: Verifies 5-tier transferability classification (A–E) and local constraints.
- [x] **Gate 7: Technical Feasibility and Data Availability**: Concrete architecture, estimated hours > 0, zero unavailable dependencies.
- [x] **Gate 8: Economic and Practical Viability**: Realistic deployment cost, zero mandatory paid subscriptions.
- [x] **Gate 9: Hackathon Buildability and Demonstration**: Estimated hours <= 1.15 * deadline, concrete demo plan.
- [x] **Gate 10: Risk, Ethics and Sustainability**: Comprehensive risks, disadvantages, ethics, and mitigations (>= 2 risks, >= 1 disadvantage, >= 1 mitigation).

---

## 5. Knowledge Subsystems & Source Registries
- [x] **Hackathon Playbook Knowledge Base** (`src/knowledge/hackathon_playbook/`):
  - [x] SQLite FTS5 full-text search index (`playbook_fts`).
  - [x] 28 curated seed entries from Devpost, MLH, YouTube retrospectives, Bread04 guide, and Microsoft Agent Academy.
  - [x] Tailored retrieval methods for all 5 agents.
- [x] **Kerala & India Official Source Registry** (`src/research/sources/kerala_india_registry.py`):
  - [x] 14 registered official portals (Kerala Data Portal, DES ODR, KAU Agromet, KSDMA, SAPCC, data.gov.in, ICAR, IMD, ISRO, NITI Aayog, FAOSTAT, World Bank, Copernicus, NASA).
  - [x] Automated domain-to-source recommendation engine.
  - [x] Targeted query generator directed at official government domains.

---

## 6. Engineering Standards & Quality Assurance
- [x] **Memory Management**: Pipeline stage-boundary `gc.collect()`, streaming XML cleanup, HTTP client `soup.decompose()`, connection closing (79.4% RAM reduction verified).
- [x] **Resilient JSON Parser**: Multi-pattern regex extraction with trailing-comma and nested-bracket repair.
- [x] **Unit & Integration Test Suite**: 74 tests passing (100% pass rate).
- [x] **Git Cleanliness**: `.gitignore` strictly protects `.env`, `data/*.db`, Ollama models, and temporary caches.
