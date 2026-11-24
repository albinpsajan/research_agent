"""Research Workspace: Dedicated execution control room and live agent telemetry."""

from __future__ import annotations

import streamlit as st

from ui.components.common import (
    badge,
    empty_state,
    hero,
    navigate_to,
)


def render() -> None:
    hero(
        "Autonomous Agent Workspace",
        "Live telemetry into the five specialist agents researching, designing, and testing hackathon candidates.",
        eyebrow="Research Execution Room",
    )

    in_progress = st.session_state.get("research_in_progress", False)
    active_session_id = st.session_state.get("current_session_id")
    current_result = st.session_state.get("current_result")
    current_multi = st.session_state.get("current_multi_result")
    live_events: list[dict] = st.session_state.get("live_events", [])
    active_agent = str(st.session_state.get("active_agent_name") or "Idle")
    try:
        progress_fraction = float(st.session_state.get("active_progress_fraction", 0.0))
    except (TypeError, ValueError):
        progress_fraction = 0.0

    if not in_progress and not current_result and not current_multi:
        empty_state(
            title="No Active Research Running",
            description="The agent workspace activates when a new research workflow is launched. "
            "You can launch a new run or review past sessions in History.",
            icon="⚙",
            cta_label="Configure New Research →",
            cta_page="New Research",
        )
        return

    # Header status banner
    status_label = "IN PROGRESS" if in_progress else "COMPLETED"
    status_kind = "teal" if in_progress else "ok"
    theme = (
        current_result.input.theme
        if current_result and hasattr(current_result, "input")
        else (current_multi.input.theme if current_multi and hasattr(current_multi, "input") else "Active Hackathon")
    )
    hackathon_name = (
        (current_result.input.name if current_result and current_result.input else None)
        or (current_multi.input.name if current_multi and current_multi.input else None)
        or "HackathonIQ Execution"
    )

    col_meta1, col_meta2 = st.columns([3, 1])
    with col_meta1:
        st.markdown(
            f"""
            <div style="margin-bottom: 14px;">
                <span style="font-size: 1.25rem; font-weight: 700; color: #ffffff;">{hackathon_name}</span>
                <div style="color: #94a3b8; font-size: 0.95rem; margin-top: 2px;">Theme: <i>{theme}</i></div>
                <div style="margin-top: 6px;">
                    {badge(f"Session {active_session_id[:8] if active_session_id else 'active'}", "neutral")}
                    {badge(status_label, status_kind)}
                    {badge("Multi-Track" if current_multi else "Single Track", "gold")}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_meta2:
        if not in_progress:
            if st.button("View Final Results →", type="primary", use_container_width=True):
                navigate_to("Results & Comparisons")

    # Overall progress bar
    st.progress(min(max(progress_fraction, 0.0), 1.0))
    st.caption(f"Pipeline Stage Progress: **{progress_fraction:.0%}** · Active Agent: **{active_agent}**")

    # The 5 Agents Stage Tracker
    st.markdown("### Agent Operational Pipeline")
    agents_info = [
        ("Agent 1", "Hackathon Intelligence", "Organizer rules, criteria & judging priorities"),
        ("Agent 2", "Domain Discovery", "Cross-disciplinary problem mapping & field evidence"),
        ("Agent 3", "Innovation Research", "GitHub/arXiv competitor audit & differentiation gaps"),
        ("Agent 4", "Solution Architect", "Technical blueprint, build timeline & demo plan"),
        ("Agent 5", "Adversarial Critic", "10-gate audit, solution refinement & honest selection"),
    ]

    cols = st.columns(5)
    for idx, (agent_id, name, desc) in enumerate(agents_info):
        with cols[idx]:
            # Determine card status
            if in_progress:
                if active_agent in name:
                    card_status = "Running"
                    status_style = "color: #14b8a6; font-weight: 600;"
                    box_border = "border: 1px solid #0d9488; background: rgba(13, 148, 136, 0.08);"
                elif progress_fraction > (idx + 1) * 0.18:
                    card_status = "Done"
                    status_style = "color: #34d399; font-weight: 600;"
                    box_border = "border: 1px solid rgba(16, 185, 129, 0.3); background: #111827;"
                else:
                    card_status = "Pending"
                    status_style = "color: #64748b;"
                    box_border = "border: 1px solid rgba(148, 163, 184, 0.12); background: #111827;"
            else:
                card_status = "Completed"
                status_style = "color: #34d399; font-weight: 600;"
                box_border = "border: 1px solid rgba(16, 185, 129, 0.3); background: #111827;"

            st.markdown(
                f"""
                <div style="{box_border} border-radius: 10px; padding: 12px; min-height: 140px; display: flex; flex-direction: column; justify-content: space-between;">
                    <div>
                        <div style="font-size: 0.72rem; text-transform: uppercase; color: #94a3b8;">{agent_id}</div>
                        <div style="font-weight: 600; font-size: 0.95rem; color: #f8fafc; margin: 2px 0 4px 0;">{name}</div>
                        <div style="font-size: 0.78rem; color: #94a3b8; line-height: 1.35;">{desc}</div>
                    </div>
                    <div style="{status_style} font-size: 0.8rem; margin-top: 8px;">● {card_status}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    tab_logs, tab_findings = st.tabs(["📋 Live Activity & Execution Log", "🔍 Live Extracted Findings"])

    with tab_logs:
        if not live_events:
            st.info("Agent activity events will stream here once execution begins.")
        else:
            log_container = st.container(height=340)
            with log_container:
                for ev in reversed(live_events[-30:]):
                    st.markdown(
                        f"""
                        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.84rem; padding: 6px 10px; background: rgba(17, 24, 39, 0.7); border-radius: 6px; margin-bottom: 4px; border-left: 3px solid #0d9488;">
                            <span style="color: #94a3b8;">[{ev.get('timestamp', 'LIVE')}]</span>
                            <span style="color: #14b8a6; font-weight: 600;"> {ev.get('stage', 'Agent')}:</span>
                            <span style="color: #f1f5f9;"> {ev.get('message', '')}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    with tab_findings:
        if current_result and current_result.domain_map:
            dm = current_result.domain_map
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                st.markdown(f"**Domains Discovered:** {dm.total_domains_explored}")
                for d in dm.domains[:6]:
                    st.markdown(f"- **{d.name}** ({d.relevance_score:.1f}/10)")
            with c_f2:
                st.markdown(f"**Real-World Problems Gathered:** {dm.total_problems_found}")
                all_probs = [p for d in dm.domains for p in d.problems]
                for p in all_probs[:6]:
                    st.markdown(f"- {p.title} *(Target: {p.affected_population[:35]}...)*")
        elif current_multi and current_multi.shared_intelligence:
            intel = current_multi.shared_intelligence
            st.markdown(f"**Shared Intelligence:** {intel.organizer_name or 'Extracted'}")
            st.markdown(f"- Theme: {intel.official_theme or 'General'}")
            st.markdown(f"- Tracks Detected: {len(current_multi.input.tracks)}")
        else:
            st.info("Agent findings will populate dynamically as domains and existing solutions are vetted.")
