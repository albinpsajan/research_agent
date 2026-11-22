"""Overview page: Mission control, system status, and recent research runs."""

from __future__ import annotations

import streamlit as st

from config.settings import get_settings
from src.orchestration.loader import load_multi_track_result, load_session_result
from src.models.pipeline import PipelineResult
from src.storage.manager import StorageManager
from ui.components.common import (
    badge,
    format_datetime,
    get_llm,
    get_repository,
    hero,
    navigate_to,
)


def render() -> None:
    settings = get_settings()
    repo = get_repository()
    llm = get_llm()
    storage = StorageManager()
    storage_report = storage.get_storage_report()
    health = llm.health()

    hero(
        "Autonomous Hackathon Research & Idea Selection",
        "Evidence over ideas. Five specialized local agents research the theme, discover domains, "
        "audit existing solutions, engineer buildable architectures, and adversarially debate to select "
        "defensible winning ideas.",
        eyebrow="Platform Overview",
        badge_text="Local-First · Zero Paid APIs",
    )

    # Active research banner if currently running or recently completed in session
    if st.session_state.get("research_in_progress"):
        st.info(
            "⏳ **Active Research in Progress:** The 5-agent pipeline is currently executing. "
            "Inspect live agent activity in the Workspace."
        )
        col_w1, _ = st.columns([1, 3])
        with col_w1:
            if st.button("Open Research Workspace", type="primary", use_container_width=True):
                navigate_to("Research Workspace")

    # High-level System & Research Metrics
    sessions = repo.list_sessions(limit=50)
    total_sessions = len(sessions)
    completed_sessions = sum(1 for s in sessions if s.get("status") in ("completed", "complete"))
    active_docs = repo.list_uploaded_documents(is_active_only=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Completed Runs", f"{completed_sessions} / {total_sessions}")
    with col2:
        model_name = health.get("active_model") or settings.ollama.model
        st.metric("Active LLM", model_name.split(":")[0], delta="Online" if health.get("available") else "Offline")
    with col3:
        st.metric("Active Documents", len(active_docs), delta="Ground Truth")
    with col4:
        st.metric("Storage Used", f"{storage_report.used_gb:.2f} GB", delta=f"{storage_report.disk_free_gb:.0f} GB Free")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Primary Action Row
    c_action1, c_action2 = st.columns([1.8, 1.2])
    with c_action1:
        st.markdown(
            """
            <div class="hiq-card" style="min-height: 160px; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <h3 style="margin: 0 0 6px 0;">Start New Hackathon Research</h3>
                    <p style="color: #94a3b8; font-size: 0.92rem; margin: 0 0 14px 0;">
                        Configure a single or multi-track hackathon brief. Set geographical targets, attach rulebooks,
                        and launch autonomous agent deliberation.
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Launch New Research Workflow →", type="primary", use_container_width=True):
            navigate_to("New Research")

    with c_action2:
        st.markdown(
            """
            <div class="hiq-card" style="min-height: 160px; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <h3 style="margin: 0 0 6px 0;">Document Ground Truth</h3>
                    <p style="color: #94a3b8; font-size: 0.92rem; margin: 0 0 14px 0;">
                        Upload PDF guidelines, problem statements, or brochures. Agents cite these as unassailable evidence.
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Manage Documents & Rulebooks →", use_container_width=True):
            navigate_to("Document Intelligence")

    st.markdown("### Recent Research Runs")
    if not sessions:
        st.markdown(
            """
            <div class="hiq-card" style="text-align: center; padding: 32px 20px;">
                <p style="color: #94a3b8; margin-bottom: 12px;">No research sessions recorded yet.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        for s in sessions[:5]:
            s_id = s["id"]
            theme = s.get("hackathon_theme", "Unnamed Theme")
            name = s.get("hackathon_name") or "Hackathon"
            status = s.get("status", "completed")
            is_multi = bool(s.get("is_multi_track"))
            created = format_datetime(s.get("created_at"))

            col_s1, col_s2 = st.columns([3.5, 1])
            with col_s1:
                track_badge = badge("Multi-Track", "teal") if is_multi else badge("Single Track", "neutral")
                status_badge = badge(status.upper(), "ok" if status in ("completed", "complete") else "warn")
                st.markdown(
                    f"""
                    <div style="padding: 10px 14px; background: #111827; border: 1px solid rgba(148, 163, 184, 0.12); border-radius: 8px; margin-bottom: 8px;">
                        <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 2px;">
                            {name} · <code>{s_id[:8]}</code> · {created}
                        </div>
                        <div style="font-weight: 600; color: #f8fafc; font-size: 1.02rem; margin-bottom: 4px;">
                            {theme}
                        </div>
                        <div>{track_badge} {status_badge}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col_s2:
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                if st.button(f"Load Results", key=f"ov_load_{s_id}", use_container_width=True):
                    _load_session_into_state(s_id, is_multi, repo)
                    navigate_to("Results & Comparisons")

    st.markdown("### The Five Autonomous Agents")
    st.markdown(
        """
        <div class="hiq-agent-grid">
            <div class="hiq-agent-card">
                <div style="color: #14b8a6; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">Agent 1</div>
                <h4 style="margin: 4px 0 6px 0; font-size: 1.05rem;">Hackathon Intelligence</h4>
                <p style="color: #94a3b8; font-size: 0.84rem; margin: 0;">Extracts organizer mission, judging criteria, past winners, sponsor preferences, and constraints.</p>
            </div>
            <div class="hiq-agent-card">
                <div style="color: #14b8a6; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">Agent 2</div>
                <h4 style="margin: 4px 0 6px 0; font-size: 1.05rem;">Domain Discovery</h4>
                <p style="color: #94a3b8; font-size: 0.84rem; margin: 0;">Dynamically maps thematic domains, discovers real-world underserved problems, and gathers citations.</p>
            </div>
            <div class="hiq-agent-card">
                <div style="color: #14b8a6; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">Agent 3</div>
                <h4 style="margin: 4px 0 6px 0; font-size: 1.05rem;">Innovation Research</h4>
                <p style="color: #94a3b8; font-size: 0.84rem; margin: 0;">Audits GitHub repos, academic papers, and existing startups to find genuine differentiation gaps.</p>
            </div>
            <div class="hiq-agent-card">
                <div style="color: #14b8a6; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">Agent 4</div>
                <h4 style="margin: 4px 0 6px 0; font-size: 1.05rem;">Solution Architect</h4>
                <p style="color: #94a3b8; font-size: 0.84rem; margin: 0;">Engineers concrete technical architectures, 36-hour build schedules, demo strategies, and APIs.</p>
            </div>
            <div class="hiq-agent-card">
                <div style="color: #14b8a6; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">Agent 5</div>
                <h4 style="margin: 4px 0 6px 0; font-size: 1.05rem;">Adversarial Critic</h4>
                <p style="color: #94a3b8; font-size: 0.84rem; margin: 0;">Tests 10 mandatory gates, triggers solution refinement loops, and independently selects the winner.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _load_session_into_state(session_id: str, is_multi_track: bool, repository) -> None:
    """Helper to populate session state with persisted result."""
    if is_multi_track:
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
    else:
        st.session_state["current_multi_result"] = None
        result = load_session_result(session_id, repository)
        if result:
            st.session_state["current_result"] = result
            st.session_state["current_session_id"] = session_id
