"""History page: Minimal ChatGPT-style session browser, loader, and manager."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components.common import (
    badge,
    empty_state,
    format_datetime,
    get_repository,
    hero,
    navigate_to,
)


def render() -> None:
    repo = get_repository()

    hero(
        "Research History",
        "Browse, review, or reload past hackathon research sessions. Each topic is securely stored in your local repository.",
        eyebrow="Session Archive",
        badge_text="Persistent SQLite",
    )

    sessions = repo.list_sessions(limit=100)

    if not sessions:
        empty_state(
            title="No Research History Recorded",
            description="You haven't conducted any hackathon research yet. Start your first research workflow to explore winning solutions.",
            icon="⏱",
            cta_label="Start New Research →",
            cta_page="New Research",
        )
        return

    # Filter & Search Controls
    col_search, col_status, col_mode = st.columns([2.5, 1.2, 1.2])
    with col_search:
        query = st.text_input(
            "Search history",
            placeholder="Search by hackathon name, theme, or ID...",
            label_visibility="collapsed",
        )
    with col_status:
        status_filter = st.selectbox(
            "Status",
            ["All Statuses", "Completed", "In Progress", "Failed"],
            label_visibility="collapsed",
        )
    with col_mode:
        mode_filter = st.selectbox(
            "Mode",
            ["All Modes", "Multi-Track", "Single Track"],
            label_visibility="collapsed",
        )

    filtered_sessions = sessions

    # Apply search filter
    if query.strip():
        q = query.strip().lower()
        filtered_sessions = [
            s
            for s in filtered_sessions
            if q in (s.get("hackathon_theme") or "").lower()
            or q in (s.get("hackathon_name") or "").lower()
            or q in (s.get("id") or "").lower()
        ]

    # Apply status filter
    if status_filter == "Completed":
        filtered_sessions = [
            s for s in filtered_sessions if (s.get("status") or "").lower() == "completed"
        ]
    elif status_filter == "In Progress":
        filtered_sessions = [
            s
            for s in filtered_sessions
            if (s.get("status") or "").lower() in ("in_progress", "running", "started")
        ]
    elif status_filter == "Failed":
        filtered_sessions = [
            s for s in filtered_sessions if (s.get("status") or "").lower() == "failed"
        ]

    # Apply mode filter
    if mode_filter == "Multi-Track":
        filtered_sessions = [s for s in filtered_sessions if s.get("is_multi_track")]
    elif mode_filter == "Single Track":
        filtered_sessions = [s for s in filtered_sessions if not s.get("is_multi_track")]

    st.markdown(
        f"<div style='color: #64748b; font-size: 0.85rem; margin-bottom: 1rem;'>"
        f"Showing <b>{len(filtered_sessions)}</b> of <b>{len(sessions)}</b> research session(s)</div>",
        unsafe_allow_html=True,
    )

    if not filtered_sessions:
        st.info("No research sessions match your search or filter criteria.")
        return

    # Compact Overview Table (Collapsible)
    frame_data = [
        {
            "Session ID": s["id"][:8],
            "Hackathon": s.get("hackathon_name") or "—",
            "Theme": s.get("hackathon_theme", ""),
            "Mode": "Multi-Track" if s.get("is_multi_track") else "Single Track",
            "Status": (s.get("status") or "completed").upper(),
            "Date": format_datetime(s.get("created_at")),
        }
        for s in filtered_sessions
    ]
    with st.expander("📊 Compact Table & Archive Overview", expanded=False):
        st.dataframe(pd.DataFrame(frame_data), use_container_width=True, hide_index=True)

    # Render each research session as ONE distinct card
    for s in filtered_sessions:
        sess_id = s["id"]
        theme = s.get("hackathon_theme") or "Untitled Theme"
        name = s.get("hackathon_name") or "Hackathon Challenge"
        status = (s.get("status") or "completed").lower()
        is_multi = bool(s.get("is_multi_track"))
        created_at_str = format_datetime(s.get("created_at"))

        # Determine tracks count
        track_count = 1
        if is_multi:
            tracks = repo.get_tracks(sess_id)
            track_count = len(tracks) if tracks else 1

        # Check for final reports
        reports = repo.get_session_reports(sess_id)
        latest_report = reports[0] if reports else None
        winner_title = (
            latest_report.get("winner_title")
            if latest_report
            else None
        )

        # Status badge styling
        if status == "completed":
            status_chip = "<span style='background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;'>COMPLETED</span>"
        elif status in ("in_progress", "running", "started"):
            status_chip = "<span style='background: rgba(13, 148, 136, 0.15); color: #14b8a6; border: 1px solid rgba(13, 148, 136, 0.3); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;'>IN PROGRESS</span>"
        else:
            status_chip = "<span style='background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;'>FAILED</span>"

        mode_text = f"Multi-Track ({track_count} tracks)" if is_multi else "Single Track"
        mode_chip = f"<span style='background: rgba(148, 163, 184, 0.12); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.2); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;'>{mode_text}</span>"
        time_chip = f"<span style='color: #64748b; font-size: 0.78rem;'>🕒 {created_at_str}</span>"

        with st.container():
            st.markdown(
                f"""
                <div style="background: #111827; border: 1px solid rgba(148, 163, 184, 0.12); border-radius: 10px; padding: 18px 20px; margin-bottom: 14px;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                        <div>
                            <div style="color: #f1f5f9; font-size: 1.05rem; font-weight: 600; margin-bottom: 2px;">
                                {theme}
                            </div>
                            <div style="color: #94a3b8; font-size: 0.85rem;">
                                {name} &nbsp;·&nbsp; ID: <code style="font-size: 0.75rem; color: #94a3b8;">{sess_id[:8]}</code>
                            </div>
                        </div>
                        <div style="display: flex; gap: 8px; align-items: center;">
                            {status_chip}
                            {mode_chip}
                            {time_chip}
                        </div>
                    </div>
                """,
                unsafe_allow_html=True,
            )

            if winner_title:
                st.markdown(
                    f"<div style='margin-bottom: 12px; font-size: 0.86rem; color: #cbd5e1;'>"
                    f"<span style='color: #f59e0b; font-weight: 600;'>Top Selected Solution:</span> {winner_title}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            # Action buttons
            col_load, col_dl, col_del, _ = st.columns([1.5, 1.8, 1.2, 3.5])

            with col_load:
                btn_label = "View Progress →" if status in ("in_progress", "running", "started") else "Load Results →"
                if st.button(btn_label, key=f"load_{sess_id}", type="primary", use_container_width=True):
                    st.session_state["target_session_to_load"] = sess_id
                    navigate_to("New Research")
                    st.rerun()

            with col_dl:
                if latest_report and latest_report.get("report_markdown"):
                    st.download_button(
                        "📄 Download Report",
                        data=latest_report["report_markdown"],
                        file_name=f"hackathoniq_{sess_id[:8]}.md",
                        mime="text/markdown",
                        key=f"dl_{sess_id}",
                        use_container_width=True,
                    )

            with col_del:
                del_confirm_key = f"confirm_delete_{sess_id}"
                if not st.session_state.get(del_confirm_key, False):
                    if st.button("🗑 Delete", key=f"del_btn_{sess_id}", use_container_width=True):
                        st.session_state[del_confirm_key] = True
                        st.rerun()
                else:
                    col_conf1, col_conf2 = st.columns(2)
                    with col_conf1:
                        if st.button("Confirm", key=f"del_yes_{sess_id}", type="primary", use_container_width=True):
                            repo.delete_session(sess_id)
                            st.session_state.pop(del_confirm_key, None)
                            st.toast(f"Session {sess_id[:8]} deleted.")
                            st.rerun()
                    with col_conf2:
                        if st.button("Cancel", key=f"del_no_{sess_id}", use_container_width=True):
                            st.session_state.pop(del_confirm_key, None)
                            st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)
