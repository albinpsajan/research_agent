"""Results page: winner, evidence, candidates, debate and report."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

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
            f"Base score {evaluation.base_score:.1f} · debate adjustment "
            f"{evaluation.debate_adjustment:+.1f} · final {evaluation.total_score:.1f}"
        )
        st.markdown("### Mandatory quality gates")
        st.dataframe(
            pd.DataFrame(gate_rows(evaluation)),
            use_container_width=True,
            hide_index=True,
        )
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
                    }
                    for item in result.winner.runner_ups
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No winning score is available for this run.")


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
