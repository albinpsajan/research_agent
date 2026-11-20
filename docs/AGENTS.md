# Agents

Five logical agents, one shared local model. Each agent has a single
responsibility, a strict output schema and evidence rules. Prompts are built by
code; model output is validated before it is trusted.

## Shared evidence discipline

All agents use `src/agents/base.py`:

- `evidence_lines(bundle)` numbers retrieved sources so the model can cite
  `evidence_indices`.
- `evidence_from_indices()` discards out-of-range or duplicate citations.
- `allowed_urls()` builds the whitelist of retrieved/user-supplied URLs.
- `sanitize_model_urls()` removes invented URLs from every URL-like field and
  logs the removal.
- `similarity()` detects near-duplicate problems and domains.

System prompts repeat the rule: use only supplied evidence; never invent facts,
statistics, judges, sponsors, projects, criteria, URLs or deadlines.

---

## Agent 1 — Hackathon Intelligence

**Module:** `src/agents/hackathon_intelligence.py`
**Purpose:** understand what the organisers actually want.

**Process**

1. Derive additional search queries from the theme, name and URLs.
2. Fetch the official website/rules pages when supplied.
3. Search for the organiser, previous editions, judges, sponsors, criteria and
   winners.
4. Extract a structured profile with the LLM.
5. Sanitize all URLs against retrieved evidence.

**Output:** `HackathonIntelligence` — organiser mission/ideology/objectives,
judges, sponsors, judging criteria, previous projects, submission requirements,
technical restrictions, recurring priorities, verified facts, assumptions and
confidence.

**Failure behaviour:** if research fails, the agent records lower confidence and
assumptions rather than fabricating facts.

---

## Agent 2 — Dynamic Domain and Problem Discovery

**Module:** `src/agents/domain_discovery.py`
**Purpose:** discover relevant domains from first principles.

**No fixed domain list.** There is no hardcoded industry taxonomy and no fixed
number of domains. The model generates domains from the theme, organiser
intelligence and retrieved research. Code only enforces bounds
(`max_domains`, `problems_per_domain`, `max_total_problems`).

**Process**

1. Ask for candidate domains with relevance type (primary, interdisciplinary,
   secondary), subdomains, interdisciplinary links and search queries.
2. Ground each domain in a `multi_search` bundle.
3. Generate problem candidates with affected people, seriousness, inadequate
   solutions, overlooked needs, emerging opportunities and future potential.
4. Convert cited evidence indices into validated `ProblemEvidence`.
5. Reject generic or unsupported problems; deduplicate by similarity.

**Output:** `DomainMap` with `DiscoveredDomain` and `ProblemCandidate` records.

**Failure behaviour:** if a domain yields no grounded problems, it remains in the
map with zero problems; the pipeline continues with the rest.

---

## Agent 3 — Global Innovation and Existing-Solution Research

**Module:** `src/agents/innovation_research.py`
**Purpose:** find out what already exists and what gap remains.

**Process**

1. Search GitHub, arXiv, OpenAlex, Crossref, Hacker News, RSS and web for each
   problem.
2. Supply repository metadata (stars, forks, language, last update, archived)
   and numbered evidence.
3. Require every existing solution to cite a valid evidence index.
4. Classify the opportunity:
   - `commonly_solved`
   - `partially_solved`
   - `existing_solution_with_important_limitations`
   - `underserved_problem`
   - `potentially_differentiated_opportunity`
   - `insufficient_evidence`
5. Record the precise gap, differentiation potential, limitations and confidence.

**Output:** `InnovationReport` with `InnovationGap` and `ExistingSolution`
records, plus tracked `ResearchSource` provenance.

**Failure behaviour:** a failed problem gets an `insufficient_evidence` gap with
the error recorded. Absence of evidence is explicitly not treated as evidence of
absence.

---

## Agent 4 — Solution Architect and Feasibility Analyst

**Module:** `src/agents/solution_architect.py`
**Purpose:** turn the strongest problems into buildable hackathon solutions.

**Process**

1. Rank problems using evidence quality, gap classification, seriousness,
   domain diversity and organiser alignment.
2. Select a cross-domain shortlist (`max_finalists`).
3. For each, design the solution, target users, differentiation, architecture,
   data/API requirements, infrastructure, dependencies, risks and mitigations.
4. Estimate realistic hours, including integration, testing and demo prep.
5. Reject candidates whose disadvantages outweigh benefits.

**Output:** `FeasibilityReport` with `CandidateSolution` records and explicit
rejections with reasons.

**Failure behaviour:** a candidate whose generation fails is recorded as
rejected with the error; the rest continue.

---

## Agent 5 — Adversarial Critic and Final Evaluator

**Module:** `src/agents/adversarial_critic.py`
**Purpose:** attack the finalists, then select independently.

**Debate (bounded, `max_debate_rounds` 1–5)**

For each finalist:

1. **Critique** — the critic must identify concrete weaknesses (originality,
   evidence, feasibility, data, competition, rules, demo) with severity,
   why it matters, and what evidence is needed.
2. **Rebuttal** — the architect must answer each criticism with cited evidence
   from the bundle, or accept the weakness.
3. **Verdict** — resolve/unresolved counts, evidence quality, a justified score
   adjustment in [-20, +5], and advance/downgrade/reject.

Guard: if unresolved critical issues remain, a positive adjustment is forced to
zero. If the rebuttal recommends rejection, the verdict cannot recommend advance.

**Scoring and gates**

The rubric service (`src/evaluation/rubric.py`) computes:

- eight weighted criteria totalling 100
- seven deterministic gates

A candidate is qualified only if **every** gate passes and the total is ≥ 60.
The final total = base score + debate adjustment.

**Independent selection**

Qualified finalists are anonymised as A–J in a session-seeded shuffled order.
The selector compares them across domains and returns one label, runner-ups,
`reject_all` and a rationale. Code validates the label, qualification and the
60-point floor. Failure to satisfy these produces **no winner**, never a
fallback winner.

**Output:** `FinalEvaluationReport` with `WinnerSelection`, per-candidate
evaluations, debates and gate outcomes.

---

## Inter-agent contract

```
HackathonInput
   → HackathonIntelligence
   → DomainMap (domains + problems + evidence)
   → InnovationReport (existing solutions + gaps)
   → FeasibilityReport (candidates + risks)
   → FinalEvaluationReport (debates + gates + winner/rejection)
   → FinalReport (24 sections, persisted)
```

Each stage persists its output to `agent_results`, so a failed run still has a
recoverable audit trail and History can reconstruct partial sessions.
