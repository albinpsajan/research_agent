"""Data access layer for HackathonIQ."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from config.logging_config import get_logger
from src.database.connection import DatabaseConnection, get_db
from src.utils.hackathon_time import utc_now

logger = get_logger("repository")


class Repository:
    """Data access layer for all HackathonIQ data operations."""

    def __init__(self, db: DatabaseConnection | None = None) -> None:
        self.db = db or get_db()

    # --- Sessions ---

    def create_session(
        self,
        theme: str,
        name: str | None = None,
        website_url: str | None = None,
        rules_url: str | None = None,
        deadline: str | None = None,
        constraints: str | None = None,
        is_multi_track: bool = False,
        multi_track_mode: str = "best_overall",
    ) -> str:
        """Create a new research session. Returns session ID."""
        session_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()]
            if "is_multi_track" in cols:
                conn.execute(
                    """INSERT INTO sessions (id, hackathon_theme, hackathon_name, website_url, 
                       rules_url, deadline, constraints, is_multi_track, multi_track_mode, status) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'created')""",
                    (
                        session_id,
                        theme,
                        name,
                        website_url,
                        rules_url,
                        deadline,
                        constraints,
                        1 if is_multi_track else 0,
                        multi_track_mode,
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO sessions (id, hackathon_theme, hackathon_name, website_url, 
                       rules_url, deadline, constraints, status) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'created')""",
                    (
                        session_id,
                        theme,
                        name,
                        website_url,
                        rules_url,
                        deadline,
                        constraints,
                    ),
                )
        logger.info(f"Created session {session_id} for theme: {theme} (multi-track={is_multi_track})")
        return session_id

    def update_session_status(self, session_id: str, status: str) -> None:
        """Update session status."""
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE sessions SET status=?, updated_at=? WHERE id=?",
                (status, utc_now().isoformat(), session_id),
            )

    def get_session(self, session_id: str) -> dict | None:
        """Get a session by ID."""
        row = self.db.fetch_one("SELECT * FROM sessions WHERE id=?", (session_id,))
        return dict(row) if row else None

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """List recent sessions."""
        rows = self.db.fetch_all(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in rows]

    # --- Agent Results ---

    def save_agent_result(
        self, session_id: str, agent_name: str, result_type: str, result_data: Any
    ) -> int:
        """Save an agent's result. Returns result ID."""
        data_json = (
            json.dumps(result_data) if not isinstance(result_data, str) else result_data
        )
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO agent_results (session_id, agent_name, result_type, result_data)
                   VALUES (?, ?, ?, ?)""",
                (session_id, agent_name, result_type, data_json),
            )
        logger.info(f"Saved {agent_name} result for session {session_id[:8]}")
        return cursor.lastrowid

    def get_agent_results(
        self, session_id: str, agent_name: str | None = None
    ) -> list[dict]:
        """Get agent results for a session."""
        if agent_name:
            rows = self.db.fetch_all(
                "SELECT * FROM agent_results WHERE session_id=? AND agent_name=? ORDER BY created_at",
                (session_id, agent_name),
            )
        else:
            rows = self.db.fetch_all(
                "SELECT * FROM agent_results WHERE session_id=? ORDER BY created_at",
                (session_id,),
            )
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["result_data"] = json.loads(d["result_data"])
            except (json.JSONDecodeError, TypeError):
                pass
            results.append(d)
        return results

    def get_latest_agent_result(
        self, session_id: str, agent_name: str, result_type: str | None = None
    ) -> dict | None:
        sql = "SELECT * FROM agent_results WHERE session_id=? AND agent_name=?"
        params: list[Any] = [session_id, agent_name]
        if result_type:
            sql += " AND result_type=?"
            params.append(result_type)
        sql += " ORDER BY id DESC LIMIT 1"
        row = self.db.fetch_one(sql, tuple(params))
        if not row:
            return None
        data = dict(row)
        try:
            data["result_data"] = json.loads(data["result_data"])
        except (json.JSONDecodeError, TypeError):
            data["result_data"] = {}
        return data

    # --- Domain map persistence ---

    def save_domain_map(self, session_id: str, domain_map: Any) -> None:
        """Persist discovered domains and problem candidates from a DomainMap."""
        with self.db.transaction() as conn:
            for domain in domain_map.domains:
                conn.execute(
                    """INSERT INTO domain_discoveries
                       (session_id, domain_name, description, relevance_type,
                        relevance_explanation, subdomains_json, confidence)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        session_id,
                        domain.name,
                        domain.description,
                        domain.relevance_type.value,
                        domain.relevance_explanation,
                        json.dumps(domain.subdomains),
                        domain.confidence,
                    ),
                )
            for problem in domain_map.problem_candidates:
                conn.execute(
                    """INSERT OR REPLACE INTO problem_candidates
                       (id, session_id, title, description, domain, subdomain,
                        seriousness, evidence_json, confidence, is_generic)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        problem.id,
                        session_id,
                        problem.title,
                        problem.description,
                        problem.domain,
                        problem.subdomain,
                        problem.seriousness,
                        json.dumps(
                            [e.model_dump(mode="json") for e in problem.evidence]
                        ),
                        problem.confidence,
                        int(problem.is_generic),
                    ),
                )

    def save_existing_solution(
        self,
        session_id: str,
        problem_candidate_id: str | None,
        solution: Any,
    ) -> int:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO existing_solutions
                   (session_id, problem_candidate_id, name, solution_type,
                    description, url, disadvantages_json, unsolved_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    problem_candidate_id,
                    solution.name,
                    solution.solution_type,
                    solution.description,
                    solution.url,
                    json.dumps(solution.disadvantages),
                    json.dumps(solution.unsolved_aspects),
                ),
            )
            return int(cursor.lastrowid)

    # --- Research Sources ---

    def save_research_source(
        self,
        session_id: str | None,
        url: str,
        title: str,
        source_type: str,
        description: str | None = None,
        metadata: dict | None = None,
        reliability: float = 0.5,
    ) -> int:
        """Save a research source, de-duplicated per session. Returns source ID."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO research_sources
                   (session_id, url, title, source_type, description, metadata_json,
                    reliability)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    url,
                    title,
                    source_type,
                    description,
                    json.dumps(metadata) if metadata else None,
                    reliability,
                ),
            )
            if cursor.lastrowid:
                return int(cursor.lastrowid)
            row = conn.execute(
                "SELECT id FROM research_sources WHERE session_id IS ? AND url=?",
                (session_id, url),
            ).fetchone()
            return int(row["id"]) if row else 0

    def get_research_sources(self, session_id: str) -> list[dict]:
        """Get all research sources for a session."""
        rows = self.db.fetch_all(
            "SELECT * FROM research_sources WHERE session_id=? ORDER BY retrieved_at",
            (session_id,),
        )
        return [dict(r) for r in rows]

    # --- Problem Candidates ---

    def save_problem_candidate(
        self,
        session_id: str,
        title: str,
        description: str,
        domain: str,
        subdomain: str | None = None,
        seriousness: str = "moderate",
        evidence: list | None = None,
        confidence: float = 0.5,
        is_generic: bool = False,
    ) -> str:
        """Save a problem candidate. Returns candidate ID."""
        candidate_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO problem_candidates (id, session_id, title, description, domain,
                   subdomain, seriousness, evidence_json, confidence, is_generic)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    candidate_id,
                    session_id,
                    title,
                    description,
                    domain,
                    subdomain,
                    seriousness,
                    json.dumps(evidence or []),
                    confidence,
                    int(is_generic),
                ),
            )
        return candidate_id

    def get_problem_candidates(self, session_id: str) -> list[dict]:
        """Get all problem candidates for a session."""
        rows = self.db.fetch_all(
            "SELECT * FROM problem_candidates WHERE session_id=? ORDER BY confidence DESC",
            (session_id,),
        )
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["evidence_json"] = (
                    json.loads(d["evidence_json"]) if d["evidence_json"] else []
                )
            except (json.JSONDecodeError, TypeError):
                d["evidence_json"] = []
            results.append(d)
        return results

    # --- Candidate Solutions ---

    def save_candidate_solution(self, session_id: str, candidate_data: dict) -> str:
        """Save a candidate solution. Returns solution ID."""
        solution_id = candidate_data.get("id") or str(uuid.uuid4())
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO candidate_solutions 
                   (id, session_id, problem_candidate_id, problem_statement, proposed_solution,
                    unique_differentiation, domain, feasibility_score, is_rejected, 
                    rejection_reason, full_data_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    solution_id,
                    session_id,
                    candidate_data.get("problem_candidate_id"),
                    candidate_data.get("problem_statement"),
                    candidate_data.get("proposed_solution"),
                    candidate_data.get("unique_differentiation"),
                    candidate_data.get("domain"),
                    candidate_data.get("feasibility_score", 0.5),
                    int(candidate_data.get("is_rejected", False)),
                    candidate_data.get("rejection_reason"),
                    json.dumps(candidate_data),
                ),
            )
        return solution_id

    def get_candidate_solutions(
        self, session_id: str, include_rejected: bool = False
    ) -> list[dict]:
        """Get candidate solutions for a session."""
        sql = "SELECT * FROM candidate_solutions WHERE session_id=?"
        if not include_rejected:
            sql += " AND is_rejected=0"
        sql += " ORDER BY feasibility_score DESC"
        rows = self.db.fetch_all(sql, (session_id,))
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["full_data_json"] = (
                    json.loads(d["full_data_json"]) if d["full_data_json"] else {}
                )
            except (json.JSONDecodeError, TypeError):
                d["full_data_json"] = {}
            results.append(d)
        return results

    # --- Evaluations ---

    def save_evaluation(
        self,
        session_id: str,
        candidate_id: str,
        total_score: float,
        all_gates_passed: bool,
        is_qualified: bool,
        rank: int | None,
        scores_json: str,
        gates_json: str,
        assessment: str,
    ) -> int:
        """Save an evaluation. Returns evaluation ID."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO evaluations (session_id, candidate_id, total_score, 
                   all_gates_passed, is_qualified, rank, scores_json, gates_json, assessment)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    candidate_id,
                    total_score,
                    int(all_gates_passed),
                    int(is_qualified),
                    rank,
                    scores_json,
                    gates_json,
                    assessment,
                ),
            )
        return cursor.lastrowid

    def get_evaluations(self, session_id: str) -> list[dict]:
        """Get all evaluations for a session."""
        rows = self.db.fetch_all(
            "SELECT * FROM evaluations WHERE session_id=? ORDER BY total_score DESC",
            (session_id,),
        )
        results = []
        for r in rows:
            d = dict(r)
            for field in ("scores_json", "gates_json"):
                try:
                    d[field] = json.loads(d[field]) if d[field] else []
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
            results.append(d)
        return results

    # --- Debate History ---

    def save_debate_round(
        self,
        session_id: str,
        candidate_id: str,
        round_number: int,
        criticism: str,
        rebuttal: str,
        evidence: list[str],
        resolved: bool,
        score_adjustment: float,
    ) -> int:
        """Save a debate round."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO debate_history (session_id, candidate_id, round_number,
                   criticism, rebuttal, evidence_json, resolved, score_adjustment)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    candidate_id,
                    round_number,
                    criticism,
                    rebuttal,
                    json.dumps(evidence),
                    int(resolved),
                    score_adjustment,
                ),
            )
        return cursor.lastrowid

    def get_debate_history(
        self, session_id: str, candidate_id: str | None = None
    ) -> list[dict]:
        """Get debate history."""
        if candidate_id:
            rows = self.db.fetch_all(
                """SELECT * FROM debate_history WHERE session_id=? AND candidate_id=? 
                   ORDER BY round_number""",
                (session_id, candidate_id),
            )
        else:
            rows = self.db.fetch_all(
                "SELECT * FROM debate_history WHERE session_id=? ORDER BY candidate_id, round_number",
                (session_id,),
            )
        return [dict(r) for r in rows]

    # --- Final Reports ---

    def save_report(
        self,
        session_id: str,
        report_json: str,
        report_markdown: str,
        has_winner: bool,
        winner_title: str | None = None,
    ) -> str:
        """Save a final report. Returns report ID."""
        report_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO final_reports (id, session_id, report_json, report_markdown,
                   has_winner, winner_title) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    report_id,
                    session_id,
                    report_json,
                    report_markdown,
                    int(has_winner),
                    winner_title,
                ),
            )
        return report_id

    def get_report(self, report_id: str) -> dict | None:
        """Get a report by ID."""
        row = self.db.fetch_one("SELECT * FROM final_reports WHERE id=?", (report_id,))
        return dict(row) if row else None

    def get_session_reports(self, session_id: str) -> list[dict]:
        """Get all reports for a session."""
        rows = self.db.fetch_all(
            "SELECT * FROM final_reports WHERE session_id=? ORDER BY created_at DESC",
            (session_id,),
        )
        return [dict(r) for r in rows]

    # --- Continuous Intelligence ---

    def save_intelligence_item(
        self,
        source_type: str,
        category: str,
        title: str,
        description: str | None = None,
        url: str | None = None,
        metadata: dict | None = None,
        topics: list | None = None,
        freshness_date: str | None = None,
    ) -> int | None:
        """Save an intelligence item. Returns its ID, or ``None`` if duplicate."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO intelligence_items
                   (source_type, category, title, description, url, metadata_json,
                    topics_json, freshness_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    source_type,
                    category,
                    title,
                    description,
                    url,
                    json.dumps(metadata) if metadata else None,
                    json.dumps(topics) if topics else None,
                    freshness_date or utc_now().isoformat(),
                ),
            )
            return (
                int(cursor.lastrowid) if cursor.rowcount and cursor.lastrowid else None
            )

    def intelligence_item_count(self) -> int:
        row = self.db.fetch_one("SELECT COUNT(*) AS n FROM intelligence_items")
        return int(row["n"]) if row else 0

    def list_intelligence_items(
        self, limit: int = 100, category: str | None = None
    ) -> list[dict]:
        sql = "SELECT * FROM intelligence_items"
        params: list[Any] = []
        if category:
            sql += " WHERE category=?"
            params.append(category)
        sql += " ORDER BY COALESCE(freshness_date, retrieved_at) DESC LIMIT ?"
        params.append(limit)
        rows = self.db.fetch_all(sql, tuple(params))
        results = []
        for row in rows:
            item = dict(row)
            for field in ("metadata_json", "topics_json"):
                try:
                    item[field] = (
                        json.loads(item[field])
                        if item[field]
                        else ({} if field == "metadata_json" else [])
                    )
                except (json.JSONDecodeError, TypeError):
                    item[field] = {} if field == "metadata_json" else []
            results.append(item)
        return results

    def get_last_refresh(self) -> dict | None:
        row = self.db.fetch_one(
            """SELECT * FROM intelligence_refresh_log
               WHERE status='success' ORDER BY completed_at DESC LIMIT 1"""
        )
        return dict(row) if row else None

    def refresh_history(self, limit: int = 20) -> list[dict]:
        rows = self.db.fetch_all(
            "SELECT * FROM intelligence_refresh_log ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    def search_intelligence_items(
        self, terms: list[str], limit: int = 30
    ) -> list[dict]:
        """Search intelligence by any of *terms* (title/description/topics)."""
        clean = [t.strip().lower() for t in terms if t and len(t.strip()) > 2][:8]
        if not clean:
            return []
        clauses = []
        params: list[Any] = []
        for term in clean:
            clauses.append(
                "(LOWER(title) LIKE ? OR LOWER(COALESCE(description,'')) LIKE ? "
                "OR LOWER(COALESCE(topics_json,'')) LIKE ?)"
            )
            like = f"%{term}%"
            params.extend([like, like, like])
        sql = (
            "SELECT * FROM intelligence_items WHERE is_stale=0 AND ("
            + " OR ".join(clauses)
            + ") ORDER BY COALESCE(freshness_date, retrieved_at) DESC LIMIT ?"
        )
        params.append(limit)
        rows = self.db.fetch_all(sql, tuple(params))
        results = []
        for row in rows:
            item = dict(row)
            for field in ("metadata_json", "topics_json"):
                try:
                    item[field] = (
                        json.loads(item[field])
                        if item[field]
                        else ({} if field == "metadata_json" else [])
                    )
                except (json.JSONDecodeError, TypeError):
                    item[field] = {} if field == "metadata_json" else []
            results.append(item)
        return results

    def mark_stale_intelligence(self, older_than_days: int) -> int:
        """Flag old intelligence rows as stale. Never deletes them."""
        cutoff = utc_now().timestamp() - older_than_days * 86_400
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """UPDATE intelligence_items SET is_stale=1
                   WHERE is_stale=0
                     AND julianday(COALESCE(freshness_date, retrieved_at)) < ?""",
                (datetime.fromtimestamp(cutoff, tz=UTC).isoformat(),),
            )
            return int(cursor.rowcount)

    def search_intelligence(
        self, query: str, category: str | None = None, limit: int = 50
    ) -> list[dict]:
        """Search intelligence items."""
        sql = "SELECT * FROM intelligence_items WHERE (title LIKE ? OR description LIKE ?)"
        params: list = [f"%{query}%", f"%{query}%"]
        if category:
            sql += " AND category=?"
            params.append(category)
        sql += " AND is_stale=0 ORDER BY retrieved_at DESC LIMIT ?"
        params.append(limit)
        rows = self.db.fetch_all(sql, tuple(params))
        return [dict(r) for r in rows]

    def log_refresh(
        self,
        source_type: str,
        items_found: int,
        items_new: int,
        status: str = "success",
        error: str | None = None,
    ) -> None:
        """Log an intelligence refresh operation."""
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO intelligence_refresh_log (source_type, items_found, items_new, 
                   status, error_message, completed_at) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    source_type,
                    items_found,
                    items_new,
                    status,
                    error,
                    utc_now().isoformat(),
                ),
            )

    # --- Multi-Track Support ---

    def save_tracks(self, session_id: str, tracks: list[Any]) -> None:
        """Save official hackathon tracks for a session."""
        with self.db.transaction() as conn:
            for t in tracks:
                track_id = t.id if hasattr(t, "id") else t.get("id")
                track_name = t.name if hasattr(t, "name") else t.get("name")
                desc = t.description if hasattr(t, "description") else t.get("description", "")
                rules = t.track_rules if hasattr(t, "track_rules") else t.get("track_rules", "")
                url = t.official_track_url if hasattr(t, "official_track_url") else t.get("official_track_url", "")
                conn.execute(
                    """INSERT OR REPLACE INTO hackathon_tracks (id, session_id, track_name, description, track_rules, official_url)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (track_id, session_id, track_name, desc, rules, url),
                )

    def get_tracks(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve tracks registered for a session."""
        rows = self.db.fetch_all(
            "SELECT * FROM hackathon_tracks WHERE session_id=? ORDER BY created_at",
            (session_id,),
        )
        return [dict(r) for r in rows]

    def save_multi_track_comparison(
        self,
        session_id: str,
        mode: str,
        winning_track_id: str | None,
        winning_candidate_id: str | None,
        comparison_data: Any,
    ) -> int:
        """Persist cross-track comparison and ranking result."""
        data_json = json.dumps(comparison_data) if not isinstance(comparison_data, str) else comparison_data
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO multi_track_comparisons (session_id, mode, winning_track_id, winning_candidate_id, comparison_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, mode, winning_track_id, winning_candidate_id, data_json),
            )
        return cursor.lastrowid

    def get_multi_track_comparison(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve the latest cross-track comparison for a session."""
        row = self.db.fetch_one(
            "SELECT * FROM multi_track_comparisons WHERE session_id=? ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        )
        if not row:
            return None
        res = dict(row)
        if "comparison_json" in res and res["comparison_json"]:
            try:
                res["comparison"] = json.loads(res["comparison_json"])
            except Exception:
                pass
        return res

