# HACKATHONIQ — AGENT RESPONSIBILITIES SPECIFICATION
## Exactly Five Logical Agents Powered by Shared Local Qwen 2.5 3B

This document defines the strict boundaries, research duties, inputs, outputs, playbook integration, and failure modes for all five logical agents operating in HackathonIQ.

---

## Agent 1: Hackathon Intelligence Agent
**Module**: `src/agents/hackathon_intelligence.py`  
**Core Purpose**: Understand what organizers, judges, and sponsors actually expect from the competition, and deconstruct stated themes into actionable problem domains.

### Inputs:
- `HackathonInput`: Theme, hackathon name, website URL, rules URL, deadline, user constraints.
- `intelligence_sources.json`: Registry of tracked hackathon platforms and judging guidelines.

### Playbook Integration:
- Ingests `HackathonPlaybookService.retrieve_for_intelligence(theme)`:
  - Lessons on distinguishing stated slogans from underlying judging intent.
  - Heuristics on honest handling of **General Theme Mode** vs **Event Mode**.
  - Guidance on sponsor API integration without gimmicky dependencies.

### Processing & Rules:
- **General Theme Mode Enforcement**: If no specific organizer or sponsors are provided, explicitly set `is_general_theme_mode = True`, record that Organizer Alignment is **NOT ASSESSABLE**, and prevent hallucinating fictional organizers.
- **Constraint Provenance**: Classify all rules into `USER_PROVIDED`, `OFFICIAL_HACKATHON`, or `AGENT_HYPOTHESIS`.

### Outputs:
- `HackathonIntelligence`: Verified organizer goals, recurring priorities, technical restrictions, judging criteria, and categorized constraints.

---

## Agent 2: Dynamic Domain & Problem Discovery Agent
**Module**: `src/agents/domain_discovery.py`  
**Core Purpose**: Dynamically discover relevant domains, subdomains, and concrete real-world problems from first principles without artificial domain limits.

### Inputs:
- Hackathon theme string.
- `HackathonIntelligence` produced by Agent 1.

### Playbook & Source Registry Integration:
- Ingests `HackathonPlaybookService.retrieve_for_domain_discovery(theme)`:
  - Lessons on concrete niche problems vs generic aggregators.
  - Requirement for >= 2 independent corroborating sources.
- Consults `KeralaIndiaSourceRegistry`:
  - Retrieves regional priority themes across Kerala's 5 agro-ecological zones (Wayanad landslides, Kuttanad floods, Palakkad drought, coastal saline ingress).
  - Matches problems to official repositories (DES ODR, KAU, KSDMA).

### Processing & Rules:
- Dynamic exploration bounded only by an exploration budget (default 15) and stopping reason (diminishing returns).
- Zero artificial domain caps (`max_domains=3` strictly forbidden).
- Enforces problem evidence association with independent search sources (`EvidenceAggregator.aggregate_problem_evidence`).

### Outputs:
- `DomainMap`: Discovered domains and a ranked list of `ProblemCandidate` objects with `kerala_relevance`, `india_relevance`, `target_districts`, and `target_geography`.

---

## Agent 3: Global Innovation & Research Agent
**Module**: `src/agents/innovation_research.py`  
**Core Purpose**: Rigorously investigate what already exists globally and locally, identify genuine innovation gaps, and classify transferability.

### Inputs:
- Top `ProblemCandidate` records from Agent 2.
- Session research context and theme.

### Playbook Integration:
- Ingests `HackathonPlaybookService.retrieve_for_innovation_research(domain)`:
  - Lessons against the "thin API wrapper" trap.
  - Heuristics on constructing competitive comparison matrices.
  - Application of the **5-Tier Adaptation Taxonomy (A–E)**.

### Processing & Rules:
- Investigates active GitHub repositories and scholarly papers across arXiv, Crossref, and OpenAlex.
- Classifies each problem opportunity: `differentiated`, `underserved`, `existing_solution_with_important_limitations`, `partially_solved`, `commonly_solved`, or `insufficient_evidence`.
- Tags transferability: Tier A (Direct), Tier B (Modified), Tier C (Redesign), Tier D (Non-transferable), Tier E (Locally originated).

### Outputs:
- `InnovationReport`: Verified existing solutions, GitHub projects, gap descriptions, and differentiation potential.

---

## Agent 4: Solution Architect & Feasibility Agent
**Module**: `src/agents/solution_architect.py`  
**Core Purpose**: Architect a practical, feasible, differentiated solution that can actually be built and demonstrated inside hackathon time limits.

### Inputs:
- High-priority problem candidates and innovation gaps.
- Available hackathon hours (`available_hours(hackathon)`).

### Playbook Integration:
- Ingests `HackathonPlaybookService.retrieve_for_solution_architect(domain, hours)`:
  - Scoping rules for 24-36 hour hackathon builds.
  - Offline-first architecture for rural deployability.
  - The **3-minute Hero User Flow** demonstration rule.
  - Zero paid cloud API mandate.

### Processing & Rules:
- Constructs complete technical architecture, API/data requirements, development complexity, and estimated hours.
- Attaches `GlobalToLocalAdaptation`, `economic_viability_notes` (zero recurring SaaS fees), and `ethical_sustainability_notes`.
- Calls `EvidenceAggregator.enrich_candidate_solution()` to guarantee zero empty schema fields.

### Outputs:
- `FeasibilityReport`: Evaluated `CandidateSolution` objects with complete architecture and demo plans.

---

## Agent 5: Adversarial Critic & Independent Evaluator
**Module**: `src/agents/adversarial_critic.py`  
**Core Purpose**: Challenge every candidate through adversarial debate, enforce all 10 mandatory quality gates, and select ONE definitive winner or honestly reject all candidates.

### Inputs:
- `CandidateSolution` objects, `ProblemCandidate` objects, `InnovationGap` records, and hackathon inputs.

### Playbook Integration:
- Ingests `HackathonPlaybookService.retrieve_for_adversarial_critic(candidate_title)`:
  - Auditing sensor resolution vs farm plot geometry (e.g. 10m Sentinel-2 vs 0.2 ha farm).
  - Interrogating synthetic datasets vs real ground truth.
  - The willingness to reject all candidates honestly when standards are unmet.

### Processing & Rules:
- Evaluates **Ten Mandatory Quality Gates**:
  1. Theme and Judging Alignment
  2. Real-World Problem Validation (>= 2 sources)
  3. Kerala and India Relevance
  4. Existing-Solution Investigation
  5. Genuine Innovation and Differentiation
  6. Global-to-Local Adaptability
  7. Technical Feasibility and Data Availability
  8. Economic and Practical Viability
  9. Hackathon Buildability and Demonstration
  10. Risk, Ethics and Sustainability
- In **General Theme Mode**, marks Organizer Alignment as NOT ASSESSABLE, calculates raw score (/90), and normalizes to 100-point scale.
- Runs multi-round adversarial debates to adjust scores based on defensibility.
- Selects exactly ONE winner if qualified, or reports honest rejection with remediation notes.

### Outputs:
- `FinalEvaluationReport`: Candidate evaluations, debate logs, gate statuses, and final winner selection.
