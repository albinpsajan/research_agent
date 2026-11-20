-- HackathonIQ Database Schema v1
-- Migration 001: Initial schema

CREATE TABLE IF NOT EXISTS migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version INTEGER NOT NULL UNIQUE,
    description TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    hackathon_theme TEXT NOT NULL,
    hackathon_name TEXT,
    website_url TEXT,
    rules_url TEXT,
    deadline TEXT,
    constraints TEXT,
    status TEXT DEFAULT 'created',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    agent_name TEXT NOT NULL,
    result_type TEXT NOT NULL,
    result_data TEXT NOT NULL,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS research_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT REFERENCES sessions(id),
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    description TEXT,
    metadata_json TEXT,
    reliability REAL DEFAULT 0.5,
    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS domain_discoveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    domain_name TEXT NOT NULL,
    description TEXT,
    relevance_type TEXT,
    relevance_explanation TEXT,
    subdomains_json TEXT,
    confidence REAL DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS problem_candidates (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    title TEXT NOT NULL,
    description TEXT,
    domain TEXT NOT NULL,
    subdomain TEXT,
    seriousness TEXT DEFAULT 'moderate',
    evidence_json TEXT,
    confidence REAL DEFAULT 0.5,
    is_generic INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS existing_solutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    problem_candidate_id TEXT REFERENCES problem_candidates(id),
    name TEXT NOT NULL,
    solution_type TEXT,
    description TEXT,
    url TEXT,
    disadvantages_json TEXT,
    unsolved_json TEXT,
    source_id INTEGER REFERENCES research_sources(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS candidate_solutions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    problem_candidate_id TEXT REFERENCES problem_candidates(id),
    problem_statement TEXT,
    proposed_solution TEXT,
    unique_differentiation TEXT,
    domain TEXT,
    feasibility_score REAL DEFAULT 0.5,
    is_rejected INTEGER DEFAULT 0,
    rejection_reason TEXT,
    full_data_json TEXT,  -- Complete CandidateSolution JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    candidate_id TEXT REFERENCES candidate_solutions(id),
    total_score REAL DEFAULT 0,
    all_gates_passed INTEGER DEFAULT 0,
    is_qualified INTEGER DEFAULT 0,
    rank INTEGER,
    scores_json TEXT,  -- JSON array of ScoreCriterion
    gates_json TEXT,   -- JSON array of QualityGate
    assessment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS debate_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    candidate_id TEXT REFERENCES candidate_solutions(id),
    round_number INTEGER NOT NULL,
    criticism TEXT,
    rebuttal TEXT,
    evidence_json TEXT,
    resolved INTEGER DEFAULT 0,
    score_adjustment REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS final_reports (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    report_json TEXT NOT NULL,
    report_markdown TEXT,
    has_winner INTEGER DEFAULT 0,
    winner_title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Continuous Intelligence tables
CREATE TABLE IF NOT EXISTS intelligence_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    url TEXT,
    metadata_json TEXT,
    topics_json TEXT,
    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    freshness_date TIMESTAMP,
    is_stale INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS intelligence_refresh_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    items_found INTEGER DEFAULT 0,
    items_new INTEGER DEFAULT 0,
    status TEXT DEFAULT 'success',
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_results_session ON agent_results(session_id);
CREATE INDEX IF NOT EXISTS idx_research_sources_session ON research_sources(session_id);
CREATE INDEX IF NOT EXISTS idx_problem_candidates_session ON problem_candidates(session_id);
CREATE INDEX IF NOT EXISTS idx_candidate_solutions_session ON candidate_solutions(session_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_session ON evaluations(session_id);
CREATE INDEX IF NOT EXISTS idx_intelligence_items_category ON intelligence_items(category);
CREATE INDEX IF NOT EXISTS idx_intelligence_items_source ON intelligence_items(source_type);
