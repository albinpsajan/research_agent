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

    def create_draft_session(self, session_id: str) -> str:
        """Ensure a draft session row exists in sessions table to satisfy foreign keys."""
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO sessions (id, hackathon_theme, status)
                   VALUES (?, '[Draft Session]', 'draft')""",
                (session_id,),
            )
        return session_id

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
        session_id: str | None = None,
    ) -> str:
        """Create a new research session. Returns session ID."""
        session_id = session_id or str(uuid.uuid4())
        with self.db.transaction() as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()]
            if "is_multi_track" in cols:
                conn.execute(
                    """INSERT OR REPLACE INTO sessions (id, hackathon_theme, hackathon_name, website_url, 
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
                    """INSERT OR REPLACE INTO sessions (id, hackathon_theme, hackathon_name, website_url, 
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

    def list_sessions(self, limit: int = 20, include_drafts: bool = False) -> list[dict]:
        """List recent sessions, excluding un-launched draft sessions by default."""
        where_clause = "" if include_drafts else "WHERE status != 'draft'"
        rows = self.db.fetch_all(
            f"SELECT * FROM sessions {where_clause} ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in rows]

    def find_session_by_theme_or_name(
        self, theme: str = "", name: str | None = None
    ) -> dict | None:
        """Find existing session matching theme or hackathon name for duplicate detection."""
        theme_clean = theme.strip().lower() if theme and theme.strip() else None
        name_clean = name.strip().lower() if name and name.strip() else None

        sessions = self.list_sessions(limit=100)
        for s in sessions:
            s_theme = (s.get("hackathon_theme") or "").strip().lower()
            s_name = (
                (s.get("hackathon_name") or "").strip().lower()
                if s.get("hackathon_name")
                else None
            )
            if theme_clean and s_theme == theme_clean:
                return s
            if name_clean and s_name and (s_name == name_clean):
                return s
        return None

    def delete_session(self, session_id: str) -> bool:
        """Cascade delete a research session and all associated child records."""
        with self.db.transaction() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            try:
                conn.execute(
                    "DELETE FROM hackathon_tracks WHERE session_id = ?", (session_id,)
                )
                conn.execute(
                    "DELETE FROM multi_track_comparisons WHERE session_id = ?",
                    (session_id,),
                )
                conn.execute(
                    "DELETE FROM document_chunks WHERE session_id = ?", (session_id,)
                )
                conn.execute(
                    "DELETE FROM document_structured_extractions WHERE session_id = ?",
                    (session_id,),
                )
                conn.execute(
                    "DELETE FROM uploaded_documents WHERE session_id = ?",
                    (session_id,),
                )
                conn.execute(
                    "DELETE FROM evaluations WHERE session_id = ?", (session_id,)
                )
                conn.execute(
                    "DELETE FROM debate_history WHERE session_id = ?", (session_id,)
                )
                conn.execute(
                    "DELETE FROM existing_solutions WHERE session_id = ?", (session_id,)
                )
                conn.execute(
                    "DELETE FROM candidate_solutions WHERE session_id = ?", (session_id,)
                )
                conn.execute(
                    "DELETE FROM problem_candidates WHERE session_id = ?", (session_id,)
                )
                conn.execute(
                    "DELETE FROM domain_discoveries WHERE session_id = ?", (session_id,)
                )
                conn.execute(
                    "DELETE FROM agent_results WHERE session_id = ?", (session_id,)
                )
                conn.execute(
                    "DELETE FROM final_reports WHERE session_id = ?", (session_id,)
                )
                conn.execute(
                    "DELETE FROM research_sources WHERE session_id = ?", (session_id,)
                )
                cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                logger.info(f"Deleted research session {session_id[:8]} and all child records")
                return cur.rowcount > 0
            finally:
                conn.execute("PRAGMA foreign_keys = ON")

    # --- Agent Results ---

    def save_agent_result(
        self, session_id: str, agent_name: str, result_type: str, result_data: Any
    ) -> int:
        """Save an agent's result. Returns result ID."""
        self.create_draft_session(session_id)
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
            if cursor.rowcount > 0 and cursor.lastrowid:
                return int(cursor.lastrowid)
            row = conn.execute(
                "SELECT id FROM research_sources WHERE session_id IS ? AND url=?",
                (session_id, url),
            ).fetchone()
            return int(row["id"]) if row else 0

    def save_research_sources_batch(
        self,
        session_id: str | None,
        sources: list[dict[str, Any]],
    ) -> list[int]:
        """Save multiple research sources in a single atomic transaction. Returns source IDs."""
        if not sources:
            return []
        ids: list[int] = []
        with self.db.transaction() as conn:
            for s in sources:
                url = s.get("url")
                if not url:
                    continue
                metadata = s.get("metadata")
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO research_sources
                       (session_id, url, title, source_type, description, metadata_json,
                        reliability)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        session_id,
                        url,
                        s.get("title", ""),
                        s.get("source_type", "research"),
                        s.get("description"),
                        json.dumps(metadata) if metadata else None,
                        float(s.get("reliability", 0.5)),
                    ),
                )
                if cursor.rowcount > 0 and cursor.lastrowid:
                    ids.append(int(cursor.lastrowid))
                else:
                    row = conn.execute(
                        "SELECT id FROM research_sources WHERE session_id IS ? AND url=?",
                        (session_id, url),
                    ).fetchone()
                    ids.append(int(row["id"]) if row else 0)
        return ids

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
        self.create_draft_session(session_id)
        with self.db.transaction() as conn:
            for t in tracks:
                track_id = t.id if hasattr(t, "id") else t.get("id")
                track_name = t.name if hasattr(t, "name") else t.get("name")
                desc = t.description if hasattr(t, "description") else t.get("description")
                rules = t.track_rules if hasattr(t, "track_rules") else t.get("track_rules")
                url = t.official_track_url if hasattr(t, "official_track_url") else t.get("official_track_url")
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
        self.create_draft_session(session_id)
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

    # --- Document Intelligence ---

    def save_uploaded_document(
        self,
        doc_id: str,
        filename: str,
        file_type: str,
        file_size: int,
        file_hash: str,
        document_type: str = "general_evidence",
        page_count: int = 1,
        extraction_method: str = "embedded_text",
        status: str = "uploaded",
        session_id: str | None = None,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Persist or update an uploaded document record."""
        warnings_json = json.dumps(warnings or [])
        metadata_json = json.dumps(metadata or {})
        if session_id:
            self.create_draft_session(session_id)
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO uploaded_documents 
                   (id, session_id, filename, file_type, file_size, file_hash, document_type,
                    page_count, extraction_method, status, warnings_json, metadata_json, is_active, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)""",
                (
                    doc_id,
                    session_id,
                    filename,
                    file_type,
                    file_size,
                    file_hash,
                    document_type,
                    page_count,
                    extraction_method,
                    status,
                    warnings_json,
                    metadata_json,
                ),
            )
        return doc_id

    def get_uploaded_document(self, doc_id: str) -> dict[str, Any] | None:
        """Fetch a single uploaded document by ID."""
        row = self.db.fetch_one("SELECT * FROM uploaded_documents WHERE id=?", (doc_id,))
        if not row:
            return None
        res = dict(row)
        res["warnings"] = json.loads(res.get("warnings_json") or "[]")
        res["metadata"] = json.loads(res.get("metadata_json") or "{}")
        return res

    def get_uploaded_document_by_hash(self, file_hash: str) -> dict[str, Any] | None:
        """Check for existing duplicate document by SHA-256 hash."""
        row = self.db.fetch_one(
            "SELECT * FROM uploaded_documents WHERE file_hash=? ORDER BY created_at DESC LIMIT 1",
            (file_hash,),
        )
        if not row:
            return None
        res = dict(row)
        res["warnings"] = json.loads(res.get("warnings_json") or "[]")
        res["metadata"] = json.loads(res.get("metadata_json") or "{}")
        return res

    def list_uploaded_documents(
        self, session_id: str | None = None, is_active_only: bool = False
    ) -> list[dict[str, Any]]:
        """List uploaded documents, optionally filtered by session or active status."""
        query = "SELECT * FROM uploaded_documents WHERE 1=1"
        params: list[Any] = []
        if session_id is not None:
            query += " AND session_id=?"
            params.append(session_id)
        if is_active_only:
            query += " AND is_active=1"
        query += " ORDER BY created_at DESC"
        rows = self.db.fetch_all(query, tuple(params))
        result = []
        for r in rows:
            d = dict(r)
            d["warnings"] = json.loads(d.get("warnings_json") or "[]")
            d["metadata"] = json.loads(d.get("metadata_json") or "{}")
            result.append(d)
        return result

    def attach_documents_to_session(self, session_id: str, doc_ids: list[str]) -> None:
        """Assign uploaded documents and chunks to a specific research session."""
        if not doc_ids:
            return
        self.create_draft_session(session_id)
        placeholders = ",".join(["?"] * len(doc_ids))
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE uploaded_documents SET session_id = ? WHERE id IN ({placeholders})",
                (session_id, *doc_ids),
            )
            conn.execute(
                f"UPDATE document_chunks SET session_id = ? WHERE document_id IN ({placeholders})",
                (session_id, *doc_ids),
            )
            conn.execute(
                f"UPDATE document_structured_extractions SET session_id = ? WHERE document_id IN ({placeholders})",
                (session_id, *doc_ids),
            )

    def update_document_status(
        self,
        doc_id: str,
        status: str,
        warnings: list[str] | None = None,
        page_count: int | None = None,
        extraction_method: str | None = None,
    ) -> None:
        """Update extraction status and optional attributes of an uploaded document."""
        updates = ["status=?", "updated_at=CURRENT_TIMESTAMP"]
        params: list[Any] = [status]
        if warnings is not None:
            updates.append("warnings_json=?")
            params.append(json.dumps(warnings))
        if page_count is not None:
            updates.append("page_count=?")
            params.append(page_count)
        if extraction_method is not None:
            updates.append("extraction_method=?")
            params.append(extraction_method)
        params.append(doc_id)
        with self.db.transaction() as conn:
            conn.execute(f"UPDATE uploaded_documents SET {', '.join(updates)} WHERE id=?", tuple(params))

    def set_document_active(self, doc_id: str, is_active: bool) -> None:
        """Toggle whether a document is in active project context."""
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE uploaded_documents SET is_active=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (1 if is_active else 0, doc_id),
            )

    def delete_uploaded_document(self, doc_id: str) -> bool:
        """Permanently delete an uploaded document and its chunks/extractions."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM document_chunks_fts WHERE document_id=?", (doc_id,))
            conn.execute("DELETE FROM document_chunks WHERE document_id=?", (doc_id,))
            conn.execute("DELETE FROM document_structured_extractions WHERE document_id=?", (doc_id,))
            cursor = conn.execute("DELETE FROM uploaded_documents WHERE id=?", (doc_id,))
            return cursor.rowcount > 0

    def save_document_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """Persist extracted document chunks and update FTS5 search index."""
        if not chunks:
            return
        for ch in chunks:
            if ch.get("session_id"):
                self.create_draft_session(ch["session_id"])
        with self.db.transaction() as conn:
            for ch in chunks:
                chunk_id = ch.get("id") or str(uuid.uuid4())
                tables_json = json.dumps(ch.get("tables", []))
                conn.execute(
                    """INSERT OR REPLACE INTO document_chunks
                       (id, document_id, session_id, page_number, chunk_index, content_type,
                        text_content, tables_json, extraction_method, confidence)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        chunk_id,
                        ch["document_id"],
                        ch.get("session_id"),
                        ch.get("page_number", 1),
                        ch.get("chunk_index", 0),
                        ch.get("content_type", "text"),
                        ch["text_content"],
                        tables_json,
                        ch.get("extraction_method", "embedded_text"),
                        ch.get("confidence", 1.0),
                    ),
                )
                conn.execute(
                    """INSERT INTO document_chunks_fts (chunk_id, document_id, text_content)
                       VALUES (?, ?, ?)""",
                    (chunk_id, ch["document_id"], ch["text_content"]),
                )

    def get_document_chunks(self, document_id: str) -> list[dict[str, Any]]:
        """Retrieve all extracted chunks for a document ordered by page and index."""
        rows = self.db.fetch_all(
            "SELECT * FROM document_chunks WHERE document_id=? ORDER BY page_number ASC, chunk_index ASC",
            (document_id,),
        )
        res = []
        for r in rows:
            d = dict(r)
            d["tables"] = json.loads(d.get("tables_json") or "[]")
            res.append(d)
        return res

    def search_document_chunks(
        self,
        query: str,
        session_id: str | None = None,
        document_ids: list[str] | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        """Full-text search over active document chunks with BM25 ranking."""
        clean_q = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
        tokens = [t for t in clean_q.split() if len(t) > 2]
        if not tokens:
            return []
        fts_match = " OR ".join(tokens[:10])

        sql = """
            SELECT c.*, d.filename, d.document_type, rank
            FROM document_chunks_fts f
            JOIN document_chunks c ON f.chunk_id = c.id
            JOIN uploaded_documents d ON c.document_id = d.id
            WHERE document_chunks_fts MATCH ?
              AND d.is_active = 1
        """
        params: list[Any] = [fts_match]
        if session_id:
            sql += " AND (c.session_id = ? OR c.session_id IS NULL)"
            params.append(session_id)
        if document_ids:
            placeholders = ",".join("?" for _ in document_ids)
            sql += f" AND c.document_id IN ({placeholders})"
            params.extend(document_ids)
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        try:
            rows = self.db.fetch_all(sql, tuple(params))
        except Exception as exc:
            logger.warning("FTS search error (%s), falling back to LIKE query: %s", clean_q, exc)
            fallback_sql = """
                SELECT c.*, d.filename, d.document_type, 1.0 as rank
                FROM document_chunks c
                JOIN uploaded_documents d ON c.document_id = d.id
                WHERE d.is_active = 1 AND (c.text_content LIKE ?)
            """
            fallback_params: list[Any] = [f"%{tokens[0]}%"]
            if session_id:
                fallback_sql += " AND (c.session_id = ? OR c.session_id IS NULL)"
                fallback_params.append(session_id)
            fallback_sql += " LIMIT ?"
            fallback_params.append(limit)
            rows = self.db.fetch_all(fallback_sql, tuple(fallback_params))

        res = []
        for r in rows:
            d = dict(r)
            d["tables"] = json.loads(d.get("tables_json") or "[]")
            res.append(d)
        return res

    def save_document_structured_extraction(
        self,
        doc_id: str,
        extraction_type: str,
        data_json: str,
        session_id: str | None = None,
    ) -> None:
        """Persist structured intelligence extracted from an uploaded document."""
        if session_id:
            self.create_draft_session(session_id)
        rec_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO document_structured_extractions
                   (id, document_id, session_id, extraction_type, data_json, created_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (rec_id, doc_id, session_id, extraction_type, data_json),
            )

    def get_document_structured_extraction(self, doc_id: str) -> dict[str, Any] | None:
        """Fetch the structured intelligence for a document."""
        row = self.db.fetch_one(
            "SELECT * FROM document_structured_extractions WHERE document_id=?",
            (doc_id,),
        )
        if not row:
            return None
        res = dict(row)
        try:
            res["data"] = json.loads(res["data_json"])
        except Exception:
            res["data"] = {}
        return res

