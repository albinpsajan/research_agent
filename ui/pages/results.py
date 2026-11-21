"""Results page: winner, evidence, candidates, debate and report."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.models.hackathon import MultiTrackMode
from src.models.multitrack import MultiTrackPipelineResult
from src.models.pipeline import PipelineResult
from ui.components.common import (
    badge,
    format_datetime,
    get_repository,
    hero,
    score_rows,
    gate_rows,
)


def render() -> None:
    multi_result: MultiTrackPipelineResult | None = st.session_state.get(
        "current_multi_result"
    )
    if multi_result:
        _render_multi_track(multi_result)
        return

    result: PipelineResult | None = st.session_state.get("current_result")
    if not result:
        hero(
            "No run loaded",
            "Start a new research run, or load a persisted session from History.",
            eyebrow="Results",
        )
        return

    winner = result.winner
    has_winner = bool(winner and winner.has_winner and winner.winner)
    hero(
        result.input.theme,
        f"{result.input.name or 'Unnamed hackathon'} · session "
        f"`{result.session_id[:8]}` · {result.status.replace('_', ' ')}",
        eyebrow="Research result",
    )

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Domains", result.domain_map.total_domains_explored if result.domain_map else 0)
    m2.metric("Problems", result.domain_map.total_problems_found if result.domain_map else 0)
    m3.metric(
        "Existing solutions",
        (
            result.innovation_report.total_solutions_found
            + result.innovation_report.total_github_projects
            if result.innovation_report
            else 0
        ),
    )
    m4.metric(
        "Finalists",
        len(result.feasibility.candidates) if result.feasibility else 0,
    )
    m5.metric(
        "Winner score",
        f"{winner.winner.total_score:.1f}" if has_winner else "—",
    )
    m6.metric("Duration", f"{result.duration_seconds / 60:.0f} min")

    if result.error:
        st.error(result.error)

    if has_winner:
        w = winner.winner
        solution = _find_solution(result, w.candidate_id)
        st.markdown(
            f"""
            <div class="hiq-winner">
                <div class="label">Independent selection · winner</div>
                <h2>{w.candidate_title}</h2>
                <div>
                    {badge(w.domain, "amber")}
                    {badge(f"{w.total_score:.1f}/100", "ok")}
                    {badge("all gates passed" if w.all_gates_passed else "gate failure", "ok" if w.all_gates_passed else "bad")}
                    {badge("debate: " + (w.debate_recommendation or "n/a"))}
                </div>
                <p class="hiq-muted">{solution.proposed_solution[:600] if solution else w.overall_assessment[:600]}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.error(
            "**No winner declared.** "
            + (
                winner.rejection_reason
                if winner and winner.rejection_reason
                else "No candidate passed every mandatory quality gate."
            )
        )
        st.caption(
            "HackathonIQ is allowed to reject every candidate. This protects you "
            "from a polished but unsupported idea."
        )

    tabs = st.tabs(
        ["Winner & scoring", "Domains & problems", "Solutions", "Debate", "Evidence", "Report"]
    )

    with tabs[0]:
        _render_scoring(result, has_winner)
    with tabs[1]:
        _render_domains(result)
    with tabs[2]:
        _render_solutions(result)
    with tabs[3]:
        _render_debate(result)
    with tabs[4]:
        _render_evidence(result)
    with tabs[5]:
        _render_report(result)


def _render_scoring(result: PipelineResult, has_winner: bool) -> None:
    winner = result.winner
    if has_winner and winner and winner.winner:
        evaluation = winner.winner
        solution = _find_solution(result, evaluation.candidate_id)

        st.markdown("### Score breakdown")
        st.dataframe(
            pd.DataFrame(score_rows(evaluation)),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Score /10": st.column_config.ProgressColumn(
                    "Score /10", min_value=0, max_value=10, format="%.1f"
                ),
                "Weighted": st.column_config.NumberColumn("Weighted", format="%.1f"),
            },
        )
        st.caption(
            f"Framework: `{evaluation.evaluation_version.value}` · "
            f"Raw {evaluation.raw_score:.1f} · Base {evaluation.base_score:.1f} · "
            f"Normalized {evaluation.normalized_score:.1f} · Debate adjustment {evaluation.debate_adjustment:+.1f} · "
            f"Final {evaluation.total_score:.1f}/100"
        )

        st.markdown("### Mandatory Quality Gates Qualification")
        passed_cnt = sum(1 for g in evaluation.quality_gates if g.status.value == "passed")
        failed_cnt = sum(1 for g in evaluation.quality_gates if g.status.value == "failed")
        insuf_cnt = sum(1 for g in evaluation.quality_gates if g.status.value == "insufficient_evidence")
        na_cnt = sum(1 for g in evaluation.quality_gates if g.status.value == "not_applicable")

        q1, q2, q3, q4 = st.columns(4)
        q1.metric("PASSED", f"{passed_cnt} / {len(evaluation.quality_gates)}")
        q2.metric("FAILED", failed_cnt)
        q3.metric("INSUFFICIENT EVIDENCE", insuf_cnt)
        q4.metric("NOT APPLICABLE", na_cnt)

        st.dataframe(
            pd.DataFrame(gate_rows(evaluation)),
            use_container_width=True,
            hide_index=True,
        )

        # Global-to-Local Adaptation Analysis Card
        if solution and (solution.kerala_adaptation or solution.target_districts):
            st.markdown("### Global-to-Local Adaptation Analysis (Kerala & India)")
            adapt = solution.kerala_adaptation
            tier_val = adapt.transferability_tier.value if adapt else "unspecified"
            districts = ", ".join(solution.target_districts) if solution.target_districts else "All Kerala Agro-Ecological Zones"
            st.markdown(
                f"""
                <div style="border: 1px solid #3b82f644; border-radius: 8px; padding: 14px; background: #0f172a; margin-bottom: 14px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 600; font-size: 1.05rem; color: #93c5fd;">
                            Transferability Taxonomy: {tier_val.replace('_', ' ').upper()}
                        </span>
                        <span style="background: #1e3a8a; color: #bfdbfe; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem;">
                            Districts: {districts}
                        </span>
                    </div>
                    <div style="margin-top: 8px; color: #e2e8f0; font-size: 0.9rem;">
                        <strong>Kerala Applicability:</strong> {adapt.kerala_applicability if adapt else 'Standard localization'}
                    </div>
                    <div style="margin-top: 6px; color: #e2e8f0; font-size: 0.9rem;">
                        <strong>India Scale Potential:</strong> {adapt.india_scale_potential if adapt else 'National open data portals'}
                    </div>
                    <div style="margin-top: 6px; color: #38bdf8; font-size: 0.9rem;">
                        <strong>Genuine Innovation Introduced:</strong> {adapt.genuine_innovation_introduced if adapt else solution.unique_differentiation}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            c_mod, c_con = st.columns(2)
            with c_mod:
                st.markdown("**Required Local Modifications**")
                mods = adapt.required_modifications if adapt else []
                for m in mods:
                    st.markdown(f"- {m}")
            with c_con:
                st.markdown("**Local Ecological/Civic Constraints**")
                cons = adapt.local_constraints if adapt else []
                for c in cons:
                    st.markdown(f"- {c}")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Strengths**")
            for item in evaluation.strengths:
                st.markdown(f"- {item}")
        with c2:
            st.markdown("**Weaknesses**")
            for item in evaluation.weaknesses:
                st.markdown(f"- {item}")
        st.markdown("**Overall assessment**")
        st.write(evaluation.overall_assessment or "Not provided.")

        if winner.runner_ups:
            st.markdown("### Runner-ups")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Candidate": item.candidate_title,
                            "Domain": item.domain,
                            "Score": item.total_score,
                            "Qualified": item.is_qualified,
                            "Version": getattr(item, "evaluation_version", "v2_ten_gate"),
                        }
                        for item in winner.runner_ups
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
    elif result.winner and result.winner.runner_ups:
        st.markdown("### Strongest alternatives")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Candidate": item.candidate_title,
                        "Domain": item.domain,
                        "Score": item.total_score,
                        "Qualified": item.is_qualified,
                        "Version": getattr(item, "evaluation_version", "v2_ten_gate"),
                    }
                    for item in result.winner.runner_ups
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No winning score is available for this run.")

    # Candidate Rejection Explanations (when no winner or rejected finalists exist)
    if not has_winner and result.final_report and result.final_report.evaluations:
        st.markdown("### Candidate Rejection & Quality Gate Audit")
        st.caption("Detailed breakdown of why each candidate failed the mandatory quality threshold.")
        for eval_item in result.final_report.evaluations:
            with st.expander(f"❌ [{eval_item.candidate_id}] {eval_item.candidate_title} (Score: {eval_item.total_score:.1f}/100)"):
                failed_gates = [g for g in eval_item.quality_gates if g.status.value in {"failed", "insufficient_evidence"}]
                if failed_gates:
                    st.error(f"Failed {len(failed_gates)} mandatory quality gate(s):")
                    for fg in failed_gates:
                        st.markdown(f"- **{fg.name}** (`{fg.status.value.upper()}`): {fg.justification}")
                else:
                    st.warning("Candidate passed gates but was rejected during adversarial debate or below qualifying score threshold.")
                st.markdown(f"**Evaluator Assessment:** {eval_item.overall_assessment}")


def _render_domains(result: PipelineResult) -> None:
    domain_map = result.domain_map
    if not domain_map or not domain_map.domains:
        st.info("No domains were discovered.")
        return
    st.caption(
        "Domains were generated from the theme and organiser intelligence — not "
        "selected from a fixed industry list."
    )
    for domain in domain_map.domains:
        problems = [
            p for p in domain_map.problem_candidates if p.domain == domain.name
        ]
        with st.expander(
            f"{domain.name} · {domain.relevance_type.value} · {len(problems)} problem(s)"
        ):
            st.markdown(domain.relevance_explanation or domain.description)
            st.markdown(
                f"**Subdomains:** {', '.join(domain.subdomains) or '—'}  \n"
                f"**Interdisciplinary links:** {', '.join(domain.interdisciplinary_links) or '—'}  \n"
                f"**Confidence:** {domain.confidence:.2f}"
            )
            for problem in problems:
                st.markdown(f"#### {problem.id}: {problem.title}")
                st.write(problem.description)
                st.markdown(
                    f"**Affected:** {', '.join(problem.affected_people) or '—'}  \n"
                    f"**Seriousness:** {problem.seriousness} · "
                    f"**Confidence:** {problem.confidence:.2f} · "
                    f"**Generic:** {'yes' if problem.is_generic else 'no'}"
                )
                if problem.evidence:
                    for evidence in problem.evidence:
                        if evidence.source_url:
                            st.markdown(
                                f"- [{evidence.source_type}] "
                                f"[{evidence.description[:160]}]({evidence.source_url}) "
                                f"· credibility {evidence.credibility:.2f}"
                            )
                else:
                    st.warning("No direct evidence retrieved — this candidate should fail the evidence gate.")


def _render_solutions(result: PipelineResult) -> None:
    feasibility = result.feasibility
    if not feasibility or not feasibility.candidates:
        st.info("No feasible solution candidates were produced.")
        return
    for candidate in feasibility.candidates:
        with st.expander(
            f"{candidate.id} · {candidate.title} · {candidate.domain} · "
            f"feasibility {candidate.feasibility_score:.2f}"
        ):
            st.markdown("**Problem**")
            st.write(candidate.problem_statement)
            st.markdown("**Proposed solution**")
            st.write(candidate.proposed_solution)
            st.markdown("**Differentiation**")
            st.write(candidate.unique_differentiation)
            c1, c2, c3 = st.columns(3)
            c1.metric("Complexity", candidate.development_complexity)
            c2.metric("Estimated hours", f"{candidate.estimated_hours:.0f}")
            c3.metric("Feasibility", f"{candidate.feasibility_score:.2f}")
            st.markdown("**Architecture**")
            st.write(candidate.technical_architecture)
            st.markdown("**Demo plan**")
            st.write(candidate.hackathon_demo_plan)
            st.markdown("**Target users**")
            st.write(", ".join(candidate.target_users) or "—")
            st.markdown("**Advantages**")
            for item in candidate.advantages:
                st.markdown(f"- {item}")
            st.markdown("**Disadvantages**")
            for item in candidate.disadvantages:
                st.markdown(f"- {item}")
            st.markdown("**Risks**")
            for risk in candidate.risks:
                st.markdown(
                    f"- **{risk.severity} / {risk.risk_type}:** {risk.description} "
                    f"— mitigation: {risk.mitigation or 'none stated'}"
                )
            if candidate.data_requirements or candidate.api_requirements:
                st.markdown("**Data and API requirements**")
                for requirement in candidate.data_requirements + candidate.api_requirements:
                    st.markdown(
                        f"- [{requirement.category}] {requirement.description} "
                        f"(availability: {requirement.availability}, cost: {requirement.cost})"
                    )
    if feasibility.rejected_candidates:
        st.markdown("### Rejected by the architect")
        for candidate in feasibility.rejected_candidates:
            st.markdown(
                f"- **{candidate.title}** — {candidate.rejection_reason or 'no reason recorded'}"
            )


def _render_debate(result: PipelineResult) -> None:
    if not result.debates:
        st.info("No debate rounds were recorded.")
        return
    st.caption(
        "Each round is bounded. The critic must supply evidence, the architect must "
        "answer with evidence, and a justified score adjustment is applied."
    )
    for debate in result.debates:
        with st.expander(
            f"{debate.candidate_id} · {debate.score_before_debate:.1f} → "
            f"{debate.score_after_debate:.1f} · {debate.recommendation}"
        ):
            st.write(debate.final_assessment or "No final assessment.")
            for round_ in debate.rounds:
                st.markdown(f"#### Round {round_.round_number}")
                st.markdown(
                    f"{badge('resolved' if round_.criticism_resolved else 'unresolved', 'ok' if round_.criticism_resolved else 'bad')} "
                    f"{badge(f'adjustment {round_.score_adjustment:+.1f}', 'amber')}"
                )
                st.markdown("**Criticism**")
                st.write(round_.criticism)
                st.markdown("**Rebuttal**")
                st.write(round_.rebuttal)
                if round_.evidence_provided:
                    st.markdown("**Evidence cited**")
                    for link in round_.evidence_provided:
                        st.markdown(f"- {link}")


def _render_evidence(result: PipelineResult) -> None:
    repository = get_repository()
    rows = repository.get_research_sources(result.session_id)
    if not rows:
        st.info("No research sources were recorded.")
        return
    st.markdown(f"### {len(rows)} tracked sources")
    st.caption(
        "Every important finding retains provenance. Retrieval dates are stored "
        "with the session."
    )
    frame = pd.DataFrame(
        [
            {
                "Title": row.get("title", ""),
                "Type": row.get("source_type", ""),
                "URL": row.get("url", ""),
                "Reliability": row.get("reliability", 0),
                "Retrieved": format_datetime(row.get("retrieved_at")),
            }
            for row in rows
        ]
    )
    st.dataframe(
        frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            "URL": st.column_config.LinkColumn("URL", display_text="Open source"),
            "Reliability": st.column_config.ProgressColumn(
                "Reliability", min_value=0.0, max_value=1.0, format="%.2f"
            ),
        },
    )


def _render_report(result: PipelineResult) -> None:
    if not result.report:
        st.info("No report was generated for this session.")
        return
    markdown = result.report.to_markdown()
    c1, c2 = st.columns([1, 1])
    with c1:
        st.download_button(
            "Download Markdown report",
            data=markdown,
            file_name=f"hackathoniq_{result.session_id[:8]}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "Download full JSON result",
            data=result.model_dump_json(indent=2),
            file_name=f"hackathoniq_{result.session_id[:8]}.json",
            mime="application/json",
            use_container_width=True,
        )
    with st.expander("Report contents", expanded=False):
        st.markdown(markdown)


def _find_solution(result: PipelineResult, candidate_id: str):
    if not result.feasibility:
        return None
    for candidate in result.feasibility.candidates:
        if candidate.id == candidate_id:
            return candidate
    return None


def _render_multi_track(multi: MultiTrackPipelineResult) -> None:
    comp = multi.comparison
    mode_a = multi.input.multi_track_mode == MultiTrackMode.BEST_OVERALL
    hero(
        multi.input.theme,
        f"{multi.input.name or 'Multi-Track Hackathon'} · session "
        f"`{multi.session_id[:8]}` · {len(multi.input.tracks)} Tracks · "
        f"{'Mode A: Best Overall Track' if mode_a else 'Mode B: Best Idea Per Track'}",
        eyebrow="Multi-Track Research Result",
    )

    # Metrics
    total_domains = sum(
        t.domain_map.total_domains_explored
        for t in multi.track_results.values()
        if t.domain_map
    )
    total_problems = sum(
        t.domain_map.total_problems_found
        for t in multi.track_results.values()
        if t.domain_map
    )
    total_solutions = sum(
        (
            t.innovation_report.total_solutions_found
            + t.innovation_report.total_github_projects
        )
        for t in multi.track_results.values()
        if t.innovation_report
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Tracks", len(multi.input.tracks))
    m2.metric("Total Domains", total_domains)
    m3.metric("Total Problems", total_problems)
    m4.metric("Solutions Scouted", total_solutions)
    m5.metric("Duration", f"{multi.duration_seconds / 60:.1f} min")

    if mode_a:
        # Mode A: Best Overall Track
        if comp and comp.overall_winning_candidate and comp.overall_winning_track:
            w = comp.overall_winning_candidate
            t = comp.overall_winning_track
            st.markdown(
                f"""
                <div class="hiq-winner">
                    <div class="label">Mode A · Best Overall Track Winner</div>
                    <h2>Track: {t.name}</h2>
                    <h3 style="margin-top: 4px; color: #f1f5f9;">{w.candidate_title}</h3>
                    <div style="margin-top: 8px;">
                        {badge(w.domain, "amber")}
                        {badge(f"{w.total_score:.1f}/100", "ok")}
                        {badge("all 10 gates passed" if w.all_gates_passed else "gate failure", "ok" if w.all_gates_passed else "bad")}
                        {badge(f"rank #1 across all {len(multi.input.tracks)} tracks")}
                    </div>
                    <p class="hiq-muted" style="margin-top: 10px;">{w.overall_assessment[:700]}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.error(
                "**No overall winner declared.** None of the candidates across all tracks passed every mandatory qualification gate."
            )
            st.caption(
                "HackathonIQ maintains an honest standard across all evaluated tracks."
            )
    else:
        # Mode B: Best Idea Per Track
        st.markdown("### Best Idea Per Track Summary")
        cols = st.columns(min(len(multi.input.tracks), 3) or 1)
        for idx, track in enumerate(multi.input.tracks):
            col = cols[idx % len(cols)]
            winner_item = comp.best_per_track.get(track.id) if comp else None
            with col:
                st.markdown(f"#### {track.name}")
                if winner_item and winner_item.evaluation:
                    ev = winner_item.evaluation
                    st.success(f"**{ev.candidate_title}**")
                    st.caption(
                        f"Score: **{ev.total_score:.1f}/100** · Domain: `{ev.domain}`"
                    )
                    st.markdown(f"*{ev.overall_assessment[:160]}...*")
                else:
                    st.warning(
                        "**No qualifying problem statement found for this track.**"
                    )
                    st.caption(
                        "Candidates in this track did not pass all mandatory quality gates."
                    )

    # Cross-track comparison table
    if comp and comp.ranked_candidates:
        st.markdown("### Cross-Track Candidates Comparison & Ranking")
        rows = []
        for rank, item in enumerate(comp.ranked_candidates, 1):
            rows.append(
                {
                    "Rank": rank,
                    "Track": item.track_name,
                    "Candidate Title": item.candidate_title,
                    "Domain": item.domain,
                    "Score /100": f"{item.total_score:.1f}",
                    "Gates Passed": (
                        "All 10 Passed" if item.all_gates_passed else "Failed Gates"
                    ),
                    "Best-Fit Track": item.best_fit_track_name or item.track_name,
                    "Overlapping": "Yes" if item.is_duplicate else "No",
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Runner-up Explanations (Mode A) or Comparative Notes
    if comp and comp.runner_up_explanations:
        with st.expander(
            "Cross-Track Runner-Up Analysis & Evaluation Rationale", expanded=False
        ):
            for exp in comp.runner_up_explanations:
                st.markdown(f"- {exp}")

    # Duplicate resolution analysis
    if comp and comp.duplicate_resolutions:
        with st.expander(
            "Cross-Track Overlap & Duplicate Deduplication", expanded=False
        ):
            st.markdown(
                "The Cross-Track Comparison Engine analyzes semantic overlap across tracks "
                "to ensure an idea is uniquely awarded to its most appropriate track."
            )
            dup_rows = []
            for d in comp.duplicate_resolutions:
                dup_rows.append(
                    {
                        "Candidate": d.candidate_title,
                        "Original Track": d.original_track_name,
                        "Assigned Track": d.best_fit_track_name,
                        "Overlaps With": d.overlapping_with_title,
                        "Similarity": f"{d.similarity_score:.2f}",
                        "Rationale": d.resolution_rationale,
                    }
                )
            st.dataframe(pd.DataFrame(dup_rows), use_container_width=True, hide_index=True)

    # Track-by-track detailed drilldown
    st.markdown("### Track-by-Track Detailed Breakdown")
    track_names = [f"Track: {t.name}" for t in multi.input.tracks]
    if track_names:
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

                t_pipe_result = PipelineResult(
                    session_id=multi.session_id,
                    input=track_res.input,
                    domain_map=track_res.domain_map,
                    innovation_report=track_res.innovation_report,
                    feasibility=track_res.feasibility,
                    debates=track_res.debates or [],
                    winner=track_res.winner,
                    report=track_res.track_report,
                    status=track_res.status,
                )
                t_has_winner = bool(
                    track_res.winner
                    and track_res.winner.has_winner
                    and track_res.winner.winner
                )

                if t_has_winner:
                    st.success(
                        f"Track Winner: **{track_res.winner.winner.candidate_title}** "
                        f"({track_res.winner.winner.total_score:.1f}/100)"
                    )
                else:
                    st.warning(
                        "**No qualifying problem statement found for this track.**"
                    )

                sub_tabs = st.tabs(
                    [
                        "Scoring & Gates",
                        "Domains & Problems",
                        "Solutions",
                        "Debate",
                        "Report",
                    ]
                )
                with sub_tabs[0]:
                    _render_scoring(t_pipe_result, t_has_winner)
                with sub_tabs[1]:
                    _render_domains(t_pipe_result)
                with sub_tabs[2]:
                    _render_solutions(t_pipe_result)
                with sub_tabs[3]:
                    _render_debate(t_pipe_result)
                with sub_tabs[4]:
                    _render_report(t_pipe_result)

    # Master Multi-Track Report Download
    st.markdown("### Master Multi-Track Comparison Report")
    if multi.master_report:
        master_md = multi.master_report.to_markdown()
        c1, c2 = st.columns([1, 1])
        with c1:
            st.download_button(
                "Download Master Multi-Track Report (Markdown)",
                data=master_md,
                file_name=f"hackathoniq_{multi.session_id[:8]}_multitrack.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "Download Multi-Track JSON Result",
                data=multi.model_dump_json(indent=2),
                file_name=f"hackathoniq_{multi.session_id[:8]}_multitrack.json",
                mime="application/json",
                use_container_width=True,
            )
        with st.expander("Master Report Preview", expanded=False):
            st.markdown(master_md[:15000])
