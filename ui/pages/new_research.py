"""New hackathon research page."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import streamlit as st

from config.settings import get_settings
from src.models.hackathon import HackathonInput
from src.models.pipeline import PipelineOptions
from src.orchestration.pipeline import HackathonPipeline
from src.research.base import ResearchError, validate_public_url
from src.storage.manager import StorageManager
from ui.components.common import get_llm, get_repository, hero, ollama_banner


def render() -> None:
    settings = get_settings()
    hero(
        "Turn a theme into one defensible idea",
        "Five specialist agents research the organisers, discover domains dynamically, "
        "investigate what already exists, design a buildable solution and attack it "
        "before recommending one problem statement.",
        eyebrow="Hackathon Research Mode",
    )
    health = ollama_banner()
    model = health.get("active_model") or settings.ollama.model
    st.caption(
        f"Local model: `{model}` · research sources: GitHub, arXiv, OpenAlex, "
        "Crossref, RSS, Wikipedia, Hacker News · no paid AI API required"
    )

    with st.form("research_form"):
        st.markdown("### The brief")
        theme = st.text_area(
            "Hackathon theme *",
            placeholder="e.g. Sustainable cities and inclusive urban life",
            height=90,
        )
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Hackathon name (optional)")
            website = st.text_input("Official website (optional)")
        with col2:
            rules = st.text_input("Rules URL (optional)")
            constraints = st.text_input(
                "Constraints (optional)", placeholder="e.g. 36 hours, teams of 4"
            )

        g1, g2 = st.columns(2)
        with g1:
            geo_priority = st.selectbox(
                "Geographical research priority",
                [
                    "Kerala First (with Indian scalability and Global taxonomy)",
                    "India National (with Global benchmarking)",
                    "Global Broad (with Indian transferability)",
                ],
                index=0,
            )
        with g2:
            kerala_districts = st.multiselect(
                "Target Kerala districts (optional)",
                [
                    "Alappuzha", "Ernakulam", "Idukki", "Kannur", "Kasaragod",
                    "Kollam", "Kottayam", "Kozhikode", "Malappuram", "Palakkad",
                    "Pathanamthitta", "Thiruvananthapuram", "Thrissur", "Wayanad",
                ],
                default=["Wayanad", "Alappuzha", "Palakkad", "Idukki"],
            )

        deadline_known = st.checkbox("I know the submission deadline", value=False)
        deadline: datetime | None = None
        if deadline_known:
            default_date = date.today() + timedelta(days=2)
            c1, c2 = st.columns(2)
            with c1:
                chosen_date = st.date_input("Deadline date", value=default_date)
            with c2:
                chosen_time = st.time_input("Deadline time (local)", value=time(18, 0))
            deadline = datetime.combine(chosen_date, chosen_time)

        with st.expander("Research controls (defaults are recommended)"):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                max_domains = st.slider(
                    "Domains", min_value=3, max_value=20, value=settings.agent.max_domains
                )
            with c2:
                per_domain = st.slider(
                    "Problems / domain",
                    min_value=1,
                    max_value=5,
                    value=settings.agent.problems_per_domain,
                )
            with c3:
                finalists = st.slider(
                    "Finalists", min_value=2, max_value=10, value=settings.agent.max_finalists
                )
            with c4:
                rounds = st.slider(
                    "Debate rounds",
                    min_value=1,
                    max_value=5,
                    value=settings.agent.max_debate_rounds,
                )
            include_ci = st.checkbox(
                "Reuse stored Continuous Intelligence signals", value=True
            )
            st.caption(
                "More domains and debate rounds improve coverage but increase local "
                "inference time. Nothing is downloaded without a storage check."
            )

        submitted = st.form_submit_button(
            "Run the five-agent research workflow", type="primary", use_container_width=True
        )

    if not submitted:
        st.markdown(
            """
            <div class="hiq-card">
                <h3>What happens when you run</h3>
                <ol>
                    <li><b>Hackathon Intelligence</b> — organiser mission, past editions, judges, sponsors, criteria.</li>
                    <li><b>Dynamic Domain Discovery</b> — fields and interdisciplinary links generated from the theme, then grounded in papers, repositories and news.</li>
                    <li><b>Global Innovation Research</b> — real GitHub projects, papers and existing products for each problem.</li>
                    <li><b>Solution Architecture</b> — cross-domain shortlist, buildable solutions, data/API needs and risks.</li>
                    <li><b>Adversarial Evaluation</b> — bounded debate, 100-point rubric, seven mandatory gates, independent final selection or an honest rejection.</li>
                </ol>
                <p class="hiq-muted">A full run typically takes 10–40 minutes on a 6 GB RTX 3050, depending on domain count and model speed. Research quality is prioritised over speed.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    if not theme or len(theme.strip()) < 3:
        st.error("Enter a hackathon theme of at least 3 characters.")
        return
    for label, url in (("Website", website), ("Rules", rules)):
        if url.strip():
            try:
                validate_public_url(url.strip())
            except ResearchError as exc:
                st.error(f"{label} URL rejected: {exc}")
                return
    if not health.get("available"):
        st.error("Start Ollama before running research.")
        return
    if not health.get("models"):
        st.error("No Ollama model is installed. Open Settings → Model to download one.")
        return

    full_constraints = []
    if constraints.strip():
        full_constraints.append(constraints.strip())
    if geo_priority:
        full_constraints.append(f"Geographical Priority: {geo_priority}")
    if kerala_districts:
        full_constraints.append(f"Target Kerala Districts: {', '.join(kerala_districts)}")

    combined_constraints = "; ".join(full_constraints) if full_constraints else None

    hackathon = HackathonInput(
        theme=theme.strip(),
        name=name.strip() or None,
        website_url=website.strip() or None,
        rules_url=rules.strip() or None,
        deadline=deadline,
        constraints=combined_constraints,
    )
    options = PipelineOptions(
        max_domains=max_domains,
        problems_per_domain=per_domain,
        max_finalists=finalists,
        max_debate_rounds=rounds,
        include_continuous_intelligence=include_ci,
    )

    progress = st.progress(0.0)
    status = st.empty()
    log = st.expander("Live activity log", expanded=True)
    events: list[str] = []

    def on_progress(stage: str, message: str, fraction: float) -> None:
        progress.progress(min(max(fraction, 0.0), 1.0))
        status.markdown(f"**{fraction:.0%}** · {message}")
        events.append(f"`{stage}` — {message}")
        log.markdown("\n\n".join(events[-12:]))

    pipeline = HackathonPipeline(
        llm=get_llm(),
        repository=get_repository(),
        progress=on_progress,
    )
    with st.spinner("Agents are researching. Do not close the tab."):
        result = pipeline.run(hackathon, options)

    if result.status == "failed":
        st.error(f"Research failed: {result.error}")
        st.info(
            "The partial session is preserved in History. Common causes: Ollama "
            "stopped, model output repeatedly invalid, or a network outage."
        )
        return

    st.session_state["current_result"] = result
    st.session_state["current_session_id"] = result.session_id
    if result.winner and result.winner.has_winner:
        st.success(
            f"Winner selected: {result.winner.winner.candidate_title} "
            f"({result.winner.winner.total_score:.1f}/100)"
        )
    else:
        st.warning(
            "No candidate passed every mandatory gate. This is an honest result; "
            "the report explains why."
        )
    st.session_state["nav_choice"] = "Results"
    st.rerun()
