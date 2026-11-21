"""Session history and persisted reports."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.models.pipeline import PipelineResult
from src.orchestration.loader import load_multi_track_result, load_session_result
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
                "Mode": "Multi-Track" if row.get("is_multi_track") else "Single Track",
                "Status": row.get("status", "unknown"),
                "Created": format_datetime(row.get("created_at")),
            }
            for row in sessions
        ]
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)

    options = {
        f"{row['id'][:8]} · {'[MULTI] ' if row.get('is_multi_track') else ''}{row['hackathon_theme'][:65]} · {row.get('status', '')}": row["id"]
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
        if session and session.get("is_multi_track"):
            multi_res = load_multi_track_result(session_id, repository)
            if multi_res:
                st.session_state["current_multi_result"] = multi_res
                st.session_state["current_session_id"] = session_id
                comp = multi_res.comparison
                winning_tid = (
                    comp.overall_winning_track.id
                    if (comp and comp.overall_winning_track)
                    else None
                )
                best_track_res = (
                    multi_res.track_results.get(winning_tid) if winning_tid else None
                )
                st.session_state["current_result"] = PipelineResult(
                    session_id=session_id,
                    input=multi_res.input,
                    intelligence=multi_res.shared_intelligence,
                    domain_map=best_track_res.domain_map if best_track_res else None,
                    innovation_report=(
                        best_track_res.innovation_report if best_track_res else None
                    ),
                    feasibility=best_track_res.feasibility if best_track_res else None,
                    debates=best_track_res.debates if best_track_res else [],
                    winner=best_track_res.winner if best_track_res else None,
                    report=multi_res.master_report,
                    status=multi_res.status,
                    started_at=multi_res.started_at,
                    completed_at=multi_res.completed_at,
                    duration_seconds=multi_res.duration_seconds,
                )
                st.session_state["nav_choice"] = "Results"
                st.rerun()
            else:
                st.error("Could not reconstruct multi-track session.")
        else:
            st.session_state["current_multi_result"] = None
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
