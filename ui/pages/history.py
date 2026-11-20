"""Session history and persisted reports."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.orchestration.loader import load_session_result
from ui.components.common import format_datetime, get_repository, hero


def render() -> None:
    hero(
        "Research history",
        "Every run, agent result, debate round, source and report is persisted in "
        "SQLite. Reload any session without re-running the research.",
        eyebrow="Archive",
    )
    repository = get_repository()
    sessions = repository.list_sessions(limit=100)
    if not sessions:
        st.info("No sessions yet. Run your first research workflow.")
        return

    frame = pd.DataFrame(
        [
            {
                "Session": row["id"][:8],
                "Theme": row["hackathon_theme"],
                "Hackathon": row.get("hackathon_name") or "—",
                "Status": row.get("status", "unknown"),
                "Created": format_datetime(row.get("created_at")),
            }
            for row in sessions
        ]
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)

    options = {
        f"{row['id'][:8]} · {row['hackathon_theme'][:70]} · {row.get('status', '')}": row["id"]
        for row in sessions
    }
    choice = st.selectbox("Load a session", list(options))
    session_id = options[choice]
    session = repository.get_session(session_id)

    c1, c2 = st.columns([1, 3])
    with c1:
        load = st.button("Load into Results", type="primary", use_container_width=True)
    with c2:
        st.caption(
            f"Created {format_datetime(session.get('created_at')) if session else '—'} · "
            f"Status {session.get('status') if session else '—'}"
        )
    if load:
        result = load_session_result(session_id, repository)
        if not result:
            st.error("Could not reconstruct this session.")
        else:
            st.session_state["current_result"] = result
            st.session_state["current_session_id"] = session_id
            st.session_state["nav_choice"] = "Results"
            st.rerun()

    reports = repository.get_session_reports(session_id)
    st.markdown("### Reports for this session")
    if not reports:
        st.caption("No report stored for this session.")
        return
    for report in reports:
        with st.expander(
            f"{report['id'][:8]} · {format_datetime(report.get('created_at'))} · "
            f"{'winner' if report.get('has_winner') else 'no winner'}"
        ):
            st.markdown(f"**Winner:** {report.get('winner_title') or '—'}")
            markdown = report.get("report_markdown") or ""
            st.download_button(
                "Download report",
                data=markdown,
                file_name=f"hackathoniq_{session_id[:8]}.md",
                mime="text/markdown",
                key=f"dl_{report['id']}",
            )
            with st.expander("Preview"):
                st.markdown(markdown[:12000])

    st.markdown("### Raw agent result counts")
    results = repository.get_agent_results(session_id)
    counts: dict[str, int] = {}
    for row in results:
        counts[row["agent_name"]] = counts.get(row["agent_name"], 0) + 1
    st.dataframe(
        pd.DataFrame(
            [{"Agent": name, "Stored results": count} for name, count in counts.items()]
        ),
        use_container_width=True,
        hide_index=True,
    )
