"""Research History page: Browse, filter, inspect, and reload persisted research sessions."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.models.pipeline import PipelineResult
from src.orchestration.loader import load_multi_track_result, load_session_result
from ui.components.common import (
    badge,
    empty_state,
    format_datetime,
    get_repository,
    hero,
    navigate_to,
)


def render() -> None:
    hero(
        "Persisted Research History & Session Archive",
        "Every research execution, agent finding, debate round, evidence citation, and report is "
        "persisted in local SQLite storage. Reload any past session into Results instantly without re-running.",
        eyebrow="Session Archive",
        badge_text="Persistent SQLite",
    )

    repository = get_repository()
    sessions = repository.list_sessions(limit=100)

    if not sessions:
        empty_state(
            title="No Research History Recorded",
            description="Run your first research workflow to start building an archive of vetted hackathon ideas.",
            icon="⏱",
            cta_label="Launch First Research Workflow →",
            cta_page="New Research",
        )
        return

    # Filter & Search Controls
    col_search, col_filter = st.columns([2.5, 1])
    with col_search:
        query = st.text_input("Filter sessions by theme or hackathon name", placeholder="e.g. BeachHack, climate, urban, health")
    with col_filter:
        mode_filter = st.selectbox("Track Mode", ["All Modes", "Multi-Track Only", "Single Track Only"])

    filtered_sessions = sessions
    if query.strip():
        q_lower = query.strip().lower()
        filtered_sessions = [
            s for s in filtered_sessions
            if q_lower in (s.get("hackathon_theme") or "").lower()
            or q_lower in (s.get("hackathon_name") or "").lower()
            or q_lower in (s.get("id") or "").lower()
        ]

    if mode_filter == "Multi-Track Only":
        filtered_sessions = [s for s in filtered_sessions if s.get("is_multi_track")]
    elif mode_filter == "Single Track Only":
        filtered_sessions = [s for s in filtered_sessions if not s.get("is_multi_track")]

    st.caption(f"Showing **{len(filtered_sessions)}** of **{len(sessions)}** recorded session(s)")

    # Session Table
    frame_data = [
        {
            "Session ID": s["id"][:8],
            "Hackathon": s.get("hackathon_name") or "—",
            "Theme": s.get("hackathon_theme", ""),
            "Mode": "Multi-Track" if s.get("is_multi_track") else "Single Track",
            "Status": (s.get("status") or "completed").upper(),
            "Timestamp": format_datetime(s.get("created_at")),
        }
        for s in filtered_sessions
    ]
    st.dataframe(pd.DataFrame(frame_data), use_container_width=True, hide_index=True)

    st.markdown("### Load Session into Results")
    options = {
        f"[{'MULTI' if s.get('is_multi_track') else 'SINGLE'}] {s['id'][:8]} · {(s.get('hackathon_theme') or 'Theme')[:60]} · {(s.get('status') or 'completed').upper()}": s["id"]
        for s in filtered_sessions
    }

    if not options:
        st.info("No matching sessions found.")
        return

    c_sel, c_btn = st.columns([3, 1])
    with c_sel:
        choice = st.selectbox("Select Session to Inspect", list(options), label_visibility="collapsed")
    with c_btn:
        load_clicked = st.button("Load into Results →", type="primary", use_container_width=True)

    session_id = options[choice]
    session = repository.get_session(session_id)

    if load_clicked:
        if session and session.get("is_multi_track"):
            multi_res = load_multi_track_result(session_id, repository)
            if multi_res:
                st.session_state["current_multi_result"] = multi_res
                st.session_state["current_session_id"] = session_id
                comp = multi_res.comparison
                winning_tid = comp.overall_winning_track.id if (comp and comp.overall_winning_track) else None
                best_track_res = multi_res.track_results.get(winning_tid) if winning_tid else None
                st.session_state["current_result"] = PipelineResult(
                    session_id=session_id,
                    input=multi_res.input,
                    intelligence=multi_res.shared_intelligence,
                    domain_map=best_track_res.domain_map if best_track_res else None,
                    innovation_report=best_track_res.innovation_report if best_track_res else None,
                    feasibility=best_track_res.feasibility if best_track_res else None,
                    debates=best_track_res.debates if best_track_res else [],
                    winner=best_track_res.winner if best_track_res else None,
                    report=multi_res.master_report,
                    status=multi_res.status,
                    started_at=multi_res.started_at,
                    completed_at=multi_res.completed_at,
                    duration_seconds=multi_res.duration_seconds,
                )
                navigate_to("Results & Comparisons")
            else:
                st.error("Could not reconstruct multi-track session.")
        else:
            st.session_state["current_multi_result"] = None
            result = load_session_result(session_id, repository)
            if result:
                st.session_state["current_result"] = result
                st.session_state["current_session_id"] = session_id
                navigate_to("Results & Comparisons")
            else:
                st.error("Could not reconstruct this single-track session.")

    # Reports for Selected Session
    reports = repository.get_session_reports(session_id)
    if reports:
        st.markdown("### Reports for Selected Session")
        for rep in reports:
            has_w = rep.get("has_winner")
            title_text = rep.get("winner_title") or "No Qualifying Winner Declared"
            with st.expander(f"Report: {rep['id'][:8]} · {format_datetime(rep.get('created_at'))} · {'Winner Selected' if has_w else 'Honest Rejection'}"):
                st.markdown(f"**Outcome:** `{title_text}`")
                md_text = rep.get("report_markdown") or ""
                st.download_button(
                    "Download Markdown Report",
                    data=md_text,
                    file_name=f"hackathoniq_{session_id[:8]}.md",
                    mime="text/markdown",
                    key=f"dl_rep_{rep['id']}",
                )
                with st.expander("Report Preview", expanded=False):
                    st.markdown(md_text[:12000])

    # Raw Agent Result Breakdown
    agent_results = repository.get_agent_results(session_id)
    if agent_results:
        st.markdown("### Stored Agent Results Audit")
        counts: dict[str, int] = {}
        for r in agent_results:
            counts[r["agent_name"]] = counts.get(r["agent_name"], 0) + 1
        st.dataframe(
            pd.DataFrame([{"Agent": k, "Artifacts Persisted": v} for k, v in counts.items()]),
            use_container_width=True,
            hide_index=True,
        )
