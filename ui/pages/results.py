"""Results and Comparisons page: Executive summary, track matrix, candidate rankings, and evidence."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.models.hackathon import MultiTrackMode
from src.models.multitrack import MultiTrackPipelineResult
from src.models.pipeline import PipelineResult
from ui.components.common import (
    badge,
    empty_state,
    format_datetime,
    gate_rows,
    get_repository,
    hero,
    score_rows,
)


def _format_duration(dur: object) -> str:
    try:
        val = float(dur)
        return f"{val / 60:.1f} min"
    except (TypeError, ValueError):
        return "—"


def render() -> None:
    multi_result: MultiTrackPipelineResult | None = st.session_state.get("current_multi_result")
    if multi_result:
        _render_multi_track(multi_result)
        return

    result: PipelineResult | None = st.session_state.get("current_result")
    if not result:
        empty_state(
            title="No Research Results Loaded",
            description="Start a new research workflow to discover, test, and select defensible ideas, "
            "or load an existing session from Research History.",
            icon="◈",
            cta_label="Launch New Research →",
            cta_page="New Research",
        )
        return

    _render_single_track(result)


def _render_single_track(result: PipelineResult) -> None:
    winner = result.winner
    has_winner = bool(winner and winner.has_winner and winner.winner)
    ev = winner.winner if has_winner else None
    solution = _find_solution(result, ev.candidate_id) if ev else None

    hero(
        result.input.theme,
        f"{result.input.name or 'Single-Track Research'} · session `{result.session_id[:8]}` · "
        f"status: {result.status.replace('_', ' ')}",
        eyebrow="Research Results & Executive Summary",
        badge_text="Single Track",
    )

    # -------------------------------------------------------------
    # SECTION A: EXECUTIVE SUMMARY (AT THE VERY TOP)
    # -------------------------------------------------------------
    exec_status = result.execution_status
    outcome = result.winner_outcome

    if exec_status == ResearchExecutionStatus.INTERRUPTED:
        st.markdown(
            f"""
            <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 8px; padding: 16px 20px; margin-bottom: 16px;">
                <div style="color: #f59e0b; font-weight: 700; font-size: 1.1rem; margin-bottom: 6px;">
                    Research was interrupted before evaluation could be completed. No final winner decision has been made.
                </div>
                <div style="color: #cbd5e1; font-size: 0.9rem; line-height: 1.5;">
                    Autonomous execution stopped before candidate generation and adversarial quality gate evaluation could conclude.
                    Available partial discoveries (domains, problem candidates, and market solutions) are preserved and displayed below.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_res, _ = st.columns([1.8, 5.2])
        with col_res:
            if st.button("▶ Resume Research", type="primary", use_container_width=True, key=f"res_single_{result.session_id}"):
                from src.orchestration.background_runner import resume_research_job
                if resume_research_job(result.session_id):
                    st.toast("Resuming research from persisted checkpoint! Tracking live progress in History...")
                    from ui.components.layout import navigate_to
                    navigate_to("History")
                    st.rerun()
                else:
                    st.error("Could not resume research session. Verify Ollama is running.")

        with st.expander("🔍 Technical Diagnostics & Checkpoint Inspection", expanded=False):
            st.markdown(
                f"""
                - **Session ID:** `{result.session_id}`
                - **Theme:** {result.input.theme}
                - **Discovered Domains:** {result.domain_map.total_domains_explored if result.domain_map else 0}
                - **Problem Statements:** {result.domain_map.total_problems_found if result.domain_map else 0}
                - **Market Solutions Scouted:** {result.innovation_report.total_solutions_found if result.innovation_report else 0}
                - **Candidate Solutions Tested:** {len(result.feasibility.candidates) if result.feasibility else 0}
                - **Gates Evaluated:** {len(result.debates) if result.debates else 0}
                - **Execution Checkpoint Status:** Safely persisted. Ready to resume next agent stage.
                """
            )

    elif exec_status == ResearchExecutionStatus.FAILED:
        st.markdown(
            f"""
            <div style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 8px; padding: 16px 20px; margin-bottom: 16px;">
                <div style="color: #ef4444; font-weight: 700; font-size: 1.1rem; margin-bottom: 6px;">
                    Research could not be completed because of an execution error.
                </div>
                <div style="color: #cbd5e1; font-size: 0.9rem; line-height: 1.5;">
                    An unexpected failure interrupted execution. Available partial findings discovered prior to failure have been preserved.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_retry, _ = st.columns([1.8, 5.2])
        with col_retry:
            if st.button("🔄 Retry / Resume Research", type="primary", use_container_width=True, key=f"retry_single_{result.session_id}"):
                from src.orchestration.background_runner import resume_research_job
                if resume_research_job(result.session_id):
                    st.toast("Retrying research from checkpoint...")
                    from ui.components.layout import navigate_to
                    navigate_to("History")
                    st.rerun()

        with st.expander("🔍 Failure Details & Error Log", expanded=True):
            st.error(result.error or "Unknown runtime execution error.")

    elif exec_status == ResearchExecutionStatus.COMPLETED and outcome == WinnerOutcome.WINNER_SELECTED and ev:
        st.markdown(
            f"""
            <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 8px; padding: 12px 18px; margin-bottom: 14px;">
                <span style="color: #10b981; font-weight: 700; font-size: 1.05rem;">Research completed. A qualifying winner was identified.</span>
            </div>
            <div class="hiq-winner">
                <div class="label">Independent Selection · Winning Idea Recommendation</div>
                <h2>{ev.candidate_title}</h2>
                <div style="margin-bottom: 12px;">
                    {badge(ev.domain, "amber")}
                    {badge(f"{ev.total_score:.1f}/100", "ok")}
                    {badge("All 10 Gates Passed" if ev.all_gates_passed else "Gate Failure", "ok" if ev.all_gates_passed else "bad")}
                    {badge(f"Debate: {ev.debate_recommendation or 'Verified'}", "teal")}
                </div>
                <p style="color: #cbd5e1; font-size: 0.96rem; line-height: 1.6; margin: 0 0 10px 0;">
                    {solution.proposed_solution if solution else ev.overall_assessment}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif exec_status == ResearchExecutionStatus.COMPLETED and outcome == WinnerOutcome.NO_QUALIFYING_WINNER:
        rejection_reason = (
            winner.rejection_reason
            if winner and winner.rejection_reason
            else "None of the generated candidates passed every mandatory quality gate."
        )
        st.markdown(
            f"""
            <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 8px; padding: 14px 18px; margin-bottom: 16px;">
                <div style="color: #f59e0b; font-weight: 700; font-size: 1.05rem; margin-bottom: 4px;">
                    Research completed. No candidate passed all mandatory quality requirements.
                </div>
                <div style="color: #cbd5e1; font-size: 0.88rem;">
                    {rejection_reason}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "HackathonIQ enforces strict empirical standards. When no candidate passes all quality gates, "
            "the platform honestly reports failure rather than fabricating an unsupported idea."
        )
    else:
        st.info("Research execution is active in the background. Tracking live progress in History.")

    # Compact Metrics Row
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Domains Explored", result.domain_map.total_domains_explored if result.domain_map else 0)
    m2.metric("Problems Scouted", result.domain_map.total_problems_found if result.domain_map else 0)
    m3.metric(
        "Existing Solutions",
        (
            result.innovation_report.total_solutions_found + result.innovation_report.total_github_projects
            if result.innovation_report
            else 0
        ),
    )
    m4.metric("Finalists Tested", len(result.feasibility.candidates) if result.feasibility else 0)
    m5.metric("Top Score", f"{ev.total_score:.1f}/100" if ev else "—")
    m6.metric("Duration", _format_duration(result.duration_seconds))

    if result.error:
        st.error(f"Execution Error: {result.error}")

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # 5 Structured Core Tabs
    tabs = st.tabs([
        "◈ 1. Executive Blueprint & Solution Details",
        "⚖ 2. Candidate Ranking & Comparison",
        "❌ 3. Rejection & Elimination Audit",
        "🌐 4. Domain & Problem Mapping",
        "📚 5. Evidence, Sources & Reports",
    ])

    with tabs[0]:
        _render_winning_blueprint(result, ev, solution)

    with tabs[1]:
        _render_candidate_ranking(result, has_winner)

    with tabs[2]:
        _render_rejection_audit(result, has_winner)

    with tabs[3]:
        _render_domains(result)

    with tabs[4]:
        _render_evidence_and_reports(result)


def _render_multi_track(multi: MultiTrackPipelineResult) -> None:
    comp = multi.comparison
    mode_a = multi.input.multi_track_mode == MultiTrackMode.BEST_OVERALL
    tracks = multi.input.tracks

    hero(
        multi.input.theme,
        f"{multi.input.name or 'Multi-Track Competition'} · session `{multi.session_id[:8]}` · "
        f"{len(tracks)} Tracks · {'Mode A: Best Overall Track' if mode_a else 'Mode B: Best Idea Per Track'}",
        eyebrow="Multi-Track Results & Comparisons",
        badge_text="Multi-Track",
    )

    # -------------------------------------------------------------
    # SECTION A: EXECUTIVE SUMMARY (AT THE VERY TOP)
    # -------------------------------------------------------------
    exec_status = multi.execution_status
    outcome = multi.winner_outcome

    if exec_status == ResearchExecutionStatus.INTERRUPTED:
        st.markdown(
            f"""
            <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 8px; padding: 16px 20px; margin-bottom: 16px;">
                <div style="color: #f59e0b; font-weight: 700; font-size: 1.1rem; margin-bottom: 6px;">
                    Research was interrupted before evaluation could be completed. No final winner decision has been made.
                </div>
                <div style="color: #cbd5e1; font-size: 0.9rem; line-height: 1.5;">
                    Autonomous multi-track research stopped before all {len(tracks)} tracks could finish.
                    Partial discoveries and completed track evaluations are preserved below.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_res, _ = st.columns([1.8, 5.2])
        with col_res:
            if st.button("▶ Resume Research", type="primary", use_container_width=True, key=f"res_multi_{multi.session_id}"):
                from src.orchestration.background_runner import resume_research_job
                if resume_research_job(multi.session_id):
                    st.toast("Resuming multi-track research from last completed track...")
                    from ui.components.layout import navigate_to
                    navigate_to("History")
                    st.rerun()

    elif exec_status == ResearchExecutionStatus.FAILED:
        st.markdown(
            f"""
            <div style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 8px; padding: 16px 20px; margin-bottom: 16px;">
                <div style="color: #ef4444; font-weight: 700; font-size: 1.1rem; margin-bottom: 6px;">
                    Research could not be completed because of an execution error.
                </div>
                <div style="color: #cbd5e1; font-size: 0.9rem; line-height: 1.5;">
                    An unexpected failure interrupted multi-track execution. Any completed track findings have been preserved.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_retry, _ = st.columns([1.8, 5.2])
        with col_retry:
            if st.button("🔄 Retry / Resume Research", type="primary", use_container_width=True, key=f"retry_multi_{multi.session_id}"):
                from src.orchestration.background_runner import resume_research_job
                if resume_research_job(multi.session_id):
                    st.toast("Retrying multi-track research...")
                    from ui.components.layout import navigate_to
                    navigate_to("History")
                    st.rerun()

    elif mode_a:
        # Mode A: Best Overall Track Winner
        if outcome == WinnerOutcome.WINNER_SELECTED and comp and (comp.overall_winner_evaluation or comp.overall_winning_candidate) and comp.overall_winning_track:
            w = comp.overall_winning_candidate
            ev = comp.overall_winner_evaluation
            t = comp.overall_winning_track
            cand_title = ev.candidate_title if ev else (w.title if w else "Winning Candidate")
            domain_name = ev.domain if ev else (w.domain if w else "Cross-Domain")
            score_text = f"{ev.total_score:.1f}/100" if ev else "N/A"
            gates_passed = ev.all_gates_passed if ev else True
            assessment = ev.overall_assessment if ev else (w.unique_differentiation if w else "")

            st.markdown(
                f"""
                <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 8px; padding: 12px 18px; margin-bottom: 14px;">
                    <span style="color: #10b981; font-weight: 700; font-size: 1.05rem;">Research completed. A qualifying winner was identified.</span>
                </div>
                <div class="hiq-winner">
                    <div class="label">Mode A · Best Overall Track Winner</div>
                    <h2>Track: {t.name}</h2>
                    <h3 style="margin-top: 4px; color: #f8fafc; font-size: 1.35rem;">{cand_title}</h3>
                    <div style="margin: 8px 0 12px 0;">
                        {badge(domain_name, "amber")}
                        {badge(score_text, "ok")}
                        {badge("All 10 Gates Passed" if gates_passed else "Gate Failure", "ok" if gates_passed else "bad")}
                        {badge(f"Rank #1 across all {len(tracks)} tracks", "teal")}
                    </div>
                    <p style="color: #cbd5e1; font-size: 0.95rem; line-height: 1.6; margin: 0;">
                        {assessment[:700]}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 8px; padding: 14px 18px; margin-bottom: 16px;">
                    <div style="color: #f59e0b; font-weight: 700; font-size: 1.05rem; margin-bottom: 4px;">
                        Research completed. No candidate passed all mandatory quality requirements.
                    </div>
                    <div style="color: #cbd5e1; font-size: 0.88rem;">
                        None of the candidate solutions across all {len(tracks)} tracks passed every mandatory qualification gate.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption(
                "HackathonIQ maintains an honest standard across all evaluated tracks."
            )
    else:
        # Mode B: Best Idea Per Track Summary at top
        st.markdown("### Best Idea Per Track Summary")
        cols = st.columns(min(len(tracks), 3) or 1)
        for idx, track in enumerate(tracks):
            col = cols[idx % len(cols)]
            ev = comp.per_track_evaluations.get(track.id) if (comp and comp.per_track_evaluations) else None
            cand = comp.per_track_winners.get(track.id) if (comp and comp.per_track_winners) else None
            with col:
                st.markdown(f"#### {track.name}")
                if ev:
                    st.success(f"**{ev.candidate_title}**")
                    st.caption(f"Score: **{ev.total_score:.1f}/100** · Domain: `{ev.domain}`")
                    st.markdown(f"*{ev.overall_assessment[:160]}...*")
                elif cand:
                    st.success(f"**{cand.title}**")
                    st.caption(f"Domain: `{cand.domain}`")
                    st.markdown(f"*{cand.unique_differentiation[:160]}...*")
                else:
                    st.warning("**No qualifying problem statement found for this track.**")
                    st.caption("Candidates in this track did not pass all mandatory quality gates.")

    # High level multi-track metrics
    total_domains = sum(t.domain_map.total_domains_explored for t in multi.track_results.values() if t.domain_map)
    total_problems = sum(t.domain_map.total_problems_found for t in multi.track_results.values() if t.domain_map)
    total_solutions = sum(
        (t.innovation_report.total_solutions_found + t.innovation_report.total_github_projects)
        for t in multi.track_results.values()
        if t.innovation_report
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Tracks Researched", len(tracks))
    m2.metric("Total Domains", total_domains)
    m3.metric("Problems Scouted", total_problems)
    m4.metric("Solutions Audited", total_solutions)
    m5.metric("Duration", _format_duration(multi.duration_seconds))

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # Multi-track organized tabs
    tabs = st.tabs([
        "⊞ 1. Track Comparison Matrix",
        "⚖ 2. Cross-Track Candidate Ranking",
        "◈ 3. Track-by-Track Detailed Breakdown",
        "🔀 4. Deduplication & Overlap Resolution",
        "📚 5. Master Multi-Track Reports",
    ])

    with tabs[0]:
        _render_track_matrix_tab(multi, comp)

    with tabs[1]:
        _render_cross_track_ranking(comp)

    with tabs[2]:
        _render_track_breakdown_tab(multi)

    with tabs[3]:
        _render_deduplication_tab(comp)

    with tabs[4]:
        _render_master_reports_tab(multi)


# -----------------------------------------------------------------------------
# DETAILED SUB-VIEW RENDERERS
# -----------------------------------------------------------------------------

def _render_winning_blueprint(result: PipelineResult, ev, solution) -> None:
    """Render Section C: Winning idea deep technical blueprint and scorecard."""
    if not ev:
        if result.execution_status == ResearchExecutionStatus.INTERRUPTED:
            st.info(
                "Solution architecture blueprint is not available because research was interrupted before candidate evaluation was completed. "
                "Explore Tab 4 (Domain & Problem Mapping) and Tab 5 (Evidence & Sources) to view partial findings, or click '▶ Resume Research' above to finish."
            )
        elif result.execution_status == ResearchExecutionStatus.FAILED:
            st.info(
                "Solution architecture blueprint is not available because an error stopped execution. "
                "Check the failure log above or retry research."
            )
        else:
            st.info("No qualifying winning idea was declared for this run.")
        return

    st.markdown("### Solution Architecture & Implementation Blueprint")

    col_sol1, col_sol2 = st.columns([1.5, 1])
    with col_sol1:
        st.markdown("#### Problem Statement & Target Community")
        st.write(solution.problem_statement if solution else "Problem challenge identified during research.")

        st.markdown("#### Proposed Solution & Core Innovation")
        st.write(solution.proposed_solution if solution else ev.overall_assessment)

        st.markdown("#### Unique Differentiation vs Existing Competitors")
        diff_text = solution.unique_differentiation if solution else "Architectural and contextual differentiation."
        st.markdown(
            f"""
            <div style="border-left: 3px solid #14b8a6; padding: 10px 14px; background: rgba(13, 148, 136, 0.08); border-radius: 6px; margin: 8px 0;">
                <span style="color: #2dd4bf; font-weight: 600;">Differentiation Factor:</span>
                <span style="color: #f1f5f9;"> {diff_text}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_sol2:
        st.markdown("#### Implementation Parameters")
        if solution:
            c_c1, c_c2 = st.columns(2)
            c_c1.metric("Build Complexity", solution.development_complexity)
            c_c2.metric("Estimated Hours", f"{solution.estimated_hours:.0f} h")
            st.markdown(f"**Feasibility Score:** `{solution.feasibility_score:.2f} / 1.0`")
            st.markdown(f"**Target Users:** {', '.join(solution.target_users) or 'General'}")

    # Technical Architecture & 3-Minute Demo Plan
    if solution:
        col_arch1, col_arch2 = st.columns(2)
        with col_arch1:
            st.markdown("#### Technical Architecture & Tech Stack")
            st.write(solution.technical_architecture or "Modular architecture designed for rapid hackathon execution.")

            if solution.data_requirements or solution.api_requirements:
                st.markdown("##### Data & API Dependencies")
                for req in solution.data_requirements + solution.api_requirements:
                    st.markdown(f"- **[{req.category}]** {req.description} *(Availability: `{req.availability}`, Cost: `{req.cost}`)*")

        with col_arch2:
            st.markdown("#### 3-Minute Live Judging Demo Plan")
            st.write(solution.hackathon_demo_plan or "Structured live demonstration showing core workflow and impact.")

            if solution.risks:
                st.markdown("##### Key Risks & Engineering Mitigations")
                for r in solution.risks[:3]:
                    st.markdown(f"- **{r.severity.upper()} ({r.risk_type}):** {r.description} — *Mitigation: {r.mitigation}*")

    # Global-to-Local Adaptation Analysis
    if solution and (solution.kerala_adaptation or solution.target_districts):
        st.markdown("#### Regional & Local Context Adaptation")
        adapt = solution.kerala_adaptation
        tier = adapt.transferability_tier.value if adapt else "General"
        districts = ", ".join(solution.target_districts) if solution.target_districts else "All Agro-Ecological Zones"
        st.markdown(
            f"""
            <div style="border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 8px; padding: 12px 16px; background: rgba(15, 23, 42, 0.6); margin-bottom: 12px;">
                <div style="color: #93c5fd; font-weight: 600;">Transferability Tier: {tier.upper()} · Districts: {districts}</div>
                <div style="margin-top: 6px; color: #cbd5e1; font-size: 0.9rem;"><b>Regional Applicability:</b> {adapt.kerala_applicability if adapt else 'Standard localization'}</div>
                <div style="margin-top: 4px; color: #cbd5e1; font-size: 0.9rem;"><b>National Scale Potential:</b> {adapt.india_scale_potential if adapt else 'National deployment via open APIs'}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Scorecard & 10 Mandatory Quality Gates
    st.markdown("### Score Breakdown & Mandatory Quality Gates")
    col_sc1, col_sc2 = st.columns([1.2, 1])
    with col_sc1:
        st.markdown("##### 100-Point Evaluation Rubric")
        st.dataframe(
            pd.DataFrame(score_rows(ev)),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Score /10": st.column_config.ProgressColumn("Score /10", min_value=0, max_value=10, format="%.1f"),
                "Weighted": st.column_config.NumberColumn("Weighted", format="%.1f"),
            },
        )
        st.caption(
            f"Raw {ev.raw_score:.1f} · Base {ev.base_score:.1f} · Normalized {ev.normalized_score:.1f} · "
            f"Debate adjustment {ev.debate_adjustment:+.1f} · Final **{ev.total_score:.1f}/100**"
        )

    with col_sc2:
        st.markdown("##### 10 Mandatory Quality Gates Qualification")
        passed_cnt = sum(1 for g in ev.quality_gates if g.status.value == "passed")
        failed_cnt = sum(1 for g in ev.quality_gates if g.status.value == "failed")
        st.markdown(f"Status: **{passed_cnt} Passed** · **{failed_cnt} Failed**")
        st.dataframe(pd.DataFrame(gate_rows(ev)), use_container_width=True, hide_index=True)


def _render_candidate_ranking(result: PipelineResult, has_winner: bool) -> None:
    """Render Section D: Candidate ranking, runner-ups, and competing approaches."""
    st.markdown("### Shortlisted Candidates Comparison")
    report = getattr(result, "report", None) or getattr(result, "final_report", None)

    if report and getattr(report, "evaluations", None):
        rows = [
            {
                "Candidate": e.candidate_title,
                "Domain": e.domain,
                "Score /100": f"{e.total_score:.1f}",
                "Qualified": "Yes" if e.is_qualified else "No",
                "Gates Passed": f"{sum(1 for g in e.quality_gates if g.status.value == 'passed')} / {len(e.quality_gates)}",
                "Disposition": getattr(e, "final_disposition", "Evaluated"),
            }
            for e in report.evaluations
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    elif result.winner and result.winner.runner_ups:
        rows = [
            {
                "Candidate": item.candidate_title,
                "Domain": item.domain,
                "Score /100": f"{item.total_score:.1f}",
                "Qualified": "Yes" if item.is_qualified else "No",
                "Version": getattr(item, "evaluation_version", "v2_ten_gate"),
            }
            for item in result.winner.runner_ups
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No candidate ranking records available.")


def _render_rejection_audit(result: PipelineResult, has_winner: bool) -> None:
    """Render Section E: Rejected candidates, failed gates, and revision attempts."""
    st.markdown("### Candidate Rejection & Quality Gate Audit")
    report = getattr(result, "report", None) or getattr(result, "final_report", None)

    if report and getattr(report, "evaluations", None):
        rejected_evals = [e for e in report.evaluations if not e.is_qualified]
        if not rejected_evals:
            st.success("All evaluated finalists passed qualification gates!")
            return

        for ev in rejected_evals:
            failed_gates = [g for g in ev.quality_gates if g.status.value in ("failed", "insufficient_evidence")]
            rounds = getattr(ev, "improvement_rounds_attempted", 0)
            with st.expander(f"❌ {ev.candidate_title} (Score: {ev.total_score:.1f}/100 · {len(failed_gates)} Gate Failures)"):
                st.markdown(f"**Improvement Rounds Attempted:** `{rounds}`")
                for fg in failed_gates:
                    st.markdown(f"- **{fg.name}** (`{fg.status.value.upper()}`): {fg.justification}")
                st.markdown(f"**Evaluator Assessment:** {ev.overall_assessment}")
    else:
        st.info("No rejected candidate records stored.")


def _render_track_matrix_tab(multi: MultiTrackPipelineResult, comp) -> None:
    """Render track summary matrix in multi-track mode."""
    st.markdown("### Track Qualification & Winner Summary Matrix")
    rows = []
    for track in multi.input.tracks:
        ev = comp.per_track_evaluations.get(track.id) if (comp and comp.per_track_evaluations) else None
        cand = comp.per_track_winners.get(track.id) if (comp and comp.per_track_winners) else None
        res = multi.track_results.get(track.id)
        has_win = bool(res and res.winner and res.winner.has_winner and res.winner.winner)

        title = ev.candidate_title if ev else (cand.title if cand else "No qualifying winner")
        score_val = f"{ev.total_score:.1f}" if ev else "—"
        gate_status = "All Passed" if (ev and ev.all_gates_passed) else ("Failed Gates" if ev else "No Qualifiers")

        rows.append({
            "Track": track.name,
            "Winning Solution": title,
            "Domain": ev.domain if ev else "—",
            "Score /100": score_val,
            "Gate Status": gate_status,
            "Outcome": "Winner Awarded" if has_win else "Honest Rejection",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_cross_track_ranking(comp) -> None:
    """Render cross-track candidate ranking table."""
    st.markdown("### Cross-Track Global Candidate Rankings")
    if not comp or not comp.ranked_candidates:
        st.info("No cross-track candidate rankings available.")
        return

    rows = [
        {
            "Rank": idx + 1,
            "Track": item.track_name,
            "Candidate Title": item.candidate_title,
            "Domain": item.domain,
            "Score /100": f"{item.total_score:.1f}",
            "Gates Passed": "All 10 Passed" if item.all_gates_passed else "Failed Gates",
            "Assigned Track": item.best_fit_track_name or item.track_name,
            "Overlap Detected": "Yes" if item.is_duplicate else "No",
        }
        for idx, item in enumerate(comp.ranked_candidates)
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_track_breakdown_tab(multi: MultiTrackPipelineResult) -> None:
    """Render per-track accordion breakdown."""
    st.markdown("### Track-by-Track Detailed Breakdown")
    track_names = [f"Track: {t.name}" for t in multi.input.tracks]
    if not track_names:
        return

    track_tabs = st.tabs(track_names)
    for idx, track in enumerate(multi.input.tracks):
        with track_tabs[idx]:
            track_res = multi.track_results.get(track.id)
            if not track_res:
                st.info(f"No result data for track {track.name}.")
                continue
            if track_res.status == "failed":
                st.error(f"Track execution failed: {track_res.error}")
                continue

            t_has_winner = bool(track_res.winner and track_res.winner.has_winner and track_res.winner.winner)
            report_obj = getattr(track_res, "report", None) or getattr(track_res, "track_report", None)
            t_pipe_result = PipelineResult(
                session_id=multi.session_id,
                input=track_res.input,
                domain_map=track_res.domain_map,
                innovation_report=track_res.innovation_report,
                feasibility=track_res.feasibility,
                debates=track_res.debates or [],
                winner=track_res.winner,
                report=report_obj,
                status=track_res.status,
            )

            if t_has_winner:
                st.success(
                    f"Track Winner: **{track_res.winner.winner.candidate_title}** "
                    f"({track_res.winner.winner.total_score:.1f}/100)"
                )
            else:
                st.warning("**No qualifying problem statement found for this track.**")

            sub_tabs = st.tabs(["Scoring & Gates", "Domains & Problems", "Solutions", "Debate", "Report"])
            with sub_tabs[0]:
                _render_winning_blueprint(t_pipe_result, track_res.winner.winner if t_has_winner else None, None)
            with sub_tabs[1]:
                _render_domains(t_pipe_result)
            with sub_tabs[2]:
                _render_solutions(t_pipe_result)
            with sub_tabs[3]:
                _render_debate(t_pipe_result)
            with sub_tabs[4]:
                _render_report(t_pipe_result)


def _render_deduplication_tab(comp) -> None:
    """Render deduplication and semantic overlap resolution."""
    st.markdown("### Semantic Overlap & Deduplication Audit")
    dups = getattr(comp, "duplicate_detections", None) or getattr(comp, "duplicate_resolutions", None)
    if not dups:
        st.info("No cross-track candidate overlap detected. All candidates were distinct.")
        return

    dup_rows = []
    for d in dups:
        if isinstance(d, dict):
            dup_rows.append({
                "Candidate": d.get("candidate_title", ""),
                "Original Track": d.get("original_track_name", ""),
                "Assigned Track": d.get("best_fit_track_name", ""),
                "Overlaps With": d.get("overlapping_with_title", ""),
                "Similarity": f"{float(d.get('similarity_score', 0.0)):.2f}",
                "Rationale": d.get("resolution_rationale", d.get("resolution_note", "")),
            })
        else:
            dup_rows.append({
                "Candidate": getattr(d, "candidate_title", ""),
                "Original Track": getattr(d, "original_track_name", ""),
                "Assigned Track": getattr(d, "best_fit_track_name", ""),
                "Overlaps With": getattr(d, "overlapping_with_title", ""),
                "Similarity": f"{getattr(d, 'similarity_score', 0.0):.2f}",
                "Rationale": getattr(d, "resolution_rationale", ""),
            })
    st.dataframe(pd.DataFrame(dup_rows), use_container_width=True, hide_index=True)


def _render_master_reports_tab(multi: MultiTrackPipelineResult) -> None:
    """Render downloads for master multi-track reports."""
    st.markdown("### Master Multi-Track Comparison Reports")
    if multi.master_report:
        master_md = multi.master_report.to_markdown()
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download Master Report (Markdown)",
                data=master_md,
                file_name=f"hackathoniq_{multi.session_id[:8]}_master.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "Download Full Multi-Track JSON",
                data=multi.model_dump_json(indent=2),
                file_name=f"hackathoniq_{multi.session_id[:8]}_multitrack.json",
                mime="application/json",
                use_container_width=True,
            )
        with st.expander("Master Report Preview", expanded=False):
            st.markdown(master_md[:15000])


def _render_domains(result: PipelineResult) -> None:
    domain_map = result.domain_map
    if not domain_map or not domain_map.domains:
        st.info("No domains were discovered.")
        return

    st.caption("Domains were discovered dynamically from the theme and organizer ground truth.")
    for domain in domain_map.domains:
        problems = [p for p in domain_map.problem_candidates if p.domain == domain.name]
        with st.expander(f"{domain.name} · {domain.relevance_type.value} · {len(problems)} Problem(s)"):
            st.markdown(domain.relevance_explanation or domain.description)
            st.markdown(
                f"**Subdomains:** {', '.join(domain.subdomains) or '—'}  \n"
                f"**Interdisciplinary Links:** {', '.join(domain.interdisciplinary_links) or '—'}  \n"
                f"**Confidence:** {domain.confidence:.2f}"
            )
            for problem in problems:
                st.markdown(f"#### {problem.id}: {problem.title}")
                st.write(problem.description)
                st.markdown(
                    f"**Affected:** {', '.join(problem.affected_people) or '—'} · "
                    f"**Seriousness:** {problem.seriousness} · **Confidence:** {problem.confidence:.2f}"
                )
                if problem.evidence:
                    for ev in problem.evidence:
                        if ev.source_url:
                            st.markdown(f"- [{ev.source_type}] [{ev.description[:140]}]({ev.source_url}) (credibility: {ev.credibility:.2f})")
                else:
                    st.warning("No direct citations attached to this problem candidate.")


def _render_solutions(result: PipelineResult) -> None:
    feasibility = result.feasibility
    if not feasibility or not feasibility.candidates:
        st.info("No solution candidates were formulated.")
        return

    for c in feasibility.candidates:
        with st.expander(f"{c.id} · {c.title} · {c.domain} (Feasibility: {c.feasibility_score:.2f})"):
            st.markdown(f"**Proposed Solution:** {c.proposed_solution}")
            st.markdown(f"**Unique Differentiation:** {c.unique_differentiation}")
            st.markdown(f"**Technical Architecture:** {c.technical_architecture}")
            st.markdown(f"**Live Demo Plan:** {c.hackathon_demo_plan}")


def _render_debate(result: PipelineResult) -> None:
    if not result.debates:
        st.info("No debate rounds recorded.")
        return

    for debate in result.debates:
        with st.expander(f"{debate.candidate_id} · {debate.score_before_debate:.1f} → {debate.score_after_debate:.1f} ({debate.recommendation})"):
            st.write(debate.final_assessment or "No debate summary.")
            for r in debate.rounds:
                st.markdown(f"**Round {r.round_number}:** Critic adjustment `{r.score_adjustment:+.1f}`")
                st.markdown(f"- **Criticism:** {r.criticism}")
                st.markdown(f"- **Rebuttal:** {r.rebuttal}")


def _render_evidence_and_reports(result: PipelineResult) -> None:
    """Render Section F: Citations, source provenance, confidence, and report downloads."""
    st.markdown("### Verified Citations & Ground-Truth Provenance")
    repo = get_repository()
    rows = repo.get_research_sources(result.session_id)

    if rows:
        frame = pd.DataFrame(
            [
                {
                    "Title": r.get("title", ""),
                    "Type": r.get("source_type", ""),
                    "URL": r.get("url", ""),
                    "Reliability": r.get("reliability", 0),
                    "Retrieved": format_datetime(r.get("retrieved_at")),
                }
                for r in rows
            ]
        )
        st.dataframe(
            frame,
            use_container_width=True,
            hide_index=True,
            column_config={
                "URL": st.column_config.LinkColumn("URL", display_text="Open source"),
                "Reliability": st.column_config.ProgressColumn("Reliability", min_value=0.0, max_value=1.0, format="%.2f"),
            },
        )
    else:
        st.info("No external source citations tracked for this session.")

    st.markdown("### Research Reports & Export")
    if result.report:
        md = result.report.to_markdown()
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download Markdown Report",
                data=md,
                file_name=f"hackathoniq_{result.session_id[:8]}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "Download Full JSON Result",
                data=result.model_dump_json(indent=2),
                file_name=f"hackathoniq_{result.session_id[:8]}.json",
                mime="application/json",
                use_container_width=True,
            )
        with st.expander("Report Contents Preview", expanded=False):
            st.markdown(md[:15000])


def _render_report(result: PipelineResult) -> None:
    _render_evidence_and_reports(result)


def _find_solution(result: PipelineResult, candidate_id: str):
    if not result.feasibility:
        return None
    for candidate in result.feasibility.candidates:
        if candidate.id == candidate_id:
            return candidate
    return None
