"""New hackathon research page."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import streamlit as st

from config.settings import get_settings
from src.knowledge.document_intelligence.service import DocumentIntelligenceService
from src.models.hackathon import HackathonInput, HackathonTrack, MultiTrackMode
from src.models.pipeline import PipelineOptions, PipelineResult
from src.orchestration.pipeline import HackathonPipeline
from src.research.base import ResearchError, validate_public_url
from ui.components.common import get_llm, get_repository, hero, ollama_banner


def render() -> None:
    settings = get_settings()
    repo = get_repository()
    service = DocumentIntelligenceService(repository=repo)

    # Retrieve auto-configuration from active uploaded documents if available
    auto_cfg: HackathonInput | None = st.session_state.get("configured_hackathon")
    if not auto_cfg:
        auto_cfg = service.get_active_auto_configuration()
        if auto_cfg:
            st.session_state["configured_hackathon"] = auto_cfg

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

    if auto_cfg:
        track_cnt = len(auto_cfg.tracks)
        track_info = f" ({track_cnt} dynamic tracks extracted)" if track_cnt else ""
        st.info(
            f"📁 **Document Intelligence Active:** Pre-filled configuration from **{auto_cfg.name or 'Uploaded Document'}**"
            f"{track_info}. All 5 agents cite active documents as primary ground truth. "
            "You can review, modify, or run research directly."
        )

    default_theme = auto_cfg.theme if auto_cfg else ""
    default_name = auto_cfg.name or "" if auto_cfg else ""
    default_website = auto_cfg.website_url or "" if auto_cfg else ""
    default_rules = auto_cfg.rules_url or "" if auto_cfg else ""
    default_constraints = auto_cfg.constraints or "" if auto_cfg else ""
    default_is_multi_track = auto_cfg.is_multi_track if auto_cfg else False
    default_mode_index = 1 if (auto_cfg and auto_cfg.multi_track_mode == MultiTrackMode.BEST_PER_TRACK) else 0
    default_num_tracks = len(auto_cfg.tracks) if (auto_cfg and auto_cfg.tracks) else 2
    default_has_deadline = bool(auto_cfg and auto_cfg.deadline)

    with st.form("research_form"):
        st.markdown("### The brief")
        theme = st.text_area(
            "Hackathon theme *",
            value=default_theme,
            placeholder="e.g. Sustainable cities and inclusive urban life",
            height=90,
        )
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Hackathon name (optional)", value=default_name)
            website = st.text_input("Official website (optional)", value=default_website)
        with col2:
            rules = st.text_input("Rules URL (optional)", value=default_rules)
            constraints = st.text_input(
                "Constraints (optional)",
                value=default_constraints,
                placeholder="e.g. 36 hours, teams of 4",
            )

        active_docs = repo.list_uploaded_documents(is_active_only=True)
        if active_docs:
            doc_summaries = [f"`{d['filename']}` ({d['document_type']})" for d in active_docs[:3]]
            st.info(f"📁 **Active Document Intelligence:** Attached {len(active_docs)} document(s): {', '.join(doc_summaries)}. All 5 agents will cite these.")
        else:
            st.caption("💡 *Tip: Upload official PDF rulebooks or research papers in the **Documents** tab to give all 5 agents primary ground truth.*")

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

        deadline_known = st.checkbox("I know the submission deadline", value=default_has_deadline)
        deadline: datetime | None = None
        if deadline_known:
            default_date = auto_cfg.deadline.date() if (auto_cfg and auto_cfg.deadline) else (date.today() + timedelta(days=2))
            default_time = auto_cfg.deadline.time() if (auto_cfg and auto_cfg.deadline) else time(18, 0)
            c1, c2 = st.columns(2)
            with c1:
                chosen_date = st.date_input("Deadline date", value=default_date)
            with c2:
                chosen_time = st.time_input("Deadline time (local)", value=default_time)
            deadline = datetime.combine(chosen_date, chosen_time)

        st.markdown("### Multi-track hackathon support")
        is_multi_track = st.checkbox(
            "Enable Multi-Track Hackathon Research",
            value=default_is_multi_track,
            help="Allows submitting multiple tracks. Evaluates each track independently and compares them.",
        )
        track_inputs: list[tuple[str, str, str, str]] = []
        multi_track_mode = MultiTrackMode.BEST_OVERALL
        if is_multi_track:
            mode_choice = st.radio(
                "Operating mode",
                [
                    "Mode A: Best Overall Track (identify the single strongest opportunity across all tracks)",
                    "Mode B: Best Idea Per Track (identify the strongest qualifying idea independently for each track)",
                ],
                index=default_mode_index,
            )
            multi_track_mode = (
                MultiTrackMode.BEST_PER_TRACK
                if "Mode B" in mode_choice
                else MultiTrackMode.BEST_OVERALL
            )
            num_tracks = st.number_input(
                "Number of tracks", min_value=1, max_value=30, value=default_num_tracks, step=1
            )
            st.caption(
                "Define tracks below. Tracks can have only a name, or full descriptions and specific constraints."
            )
            for i in range(int(num_tracks)):
                track_obj = auto_cfg.tracks[i] if (auto_cfg and i < len(auto_cfg.tracks)) else None
                t_def_name = track_obj.name if track_obj else ""
                t_def_desc = track_obj.description if track_obj else ""
                t_def_rules = track_obj.track_rules if track_obj else ""
                t_def_url = track_obj.official_track_url if track_obj else ""

                expander_title = f"Track {i+1} Details: {t_def_name}" if t_def_name else f"Track {i+1} Details"
                with st.expander(expander_title, expanded=(i < 3)):
                    t_name = st.text_input(
                        f"Track {i+1} Name *",
                        value=t_def_name,
                        key=f"t_name_{i}",
                        placeholder=f"e.g. Healthcare AI / Track {i+1}",
                    )
                    t_desc = st.text_area(
                        f"Track {i+1} Description (optional)",
                        value=t_def_desc,
                        key=f"t_desc_{i}",
                        height=65,
                    )
                    c_tr1, c_tr2 = st.columns(2)
                    with c_tr1:
                        t_rules = st.text_input(
                            f"Track {i+1} Specific Rules / Constraints (optional)",
                            value=t_def_rules,
                            key=f"t_rules_{i}",
                        )
                    with c_tr2:
                        t_url = st.text_input(
                            f"Track {i+1} Official URL (optional)",
                            value=t_def_url,
                            key=f"t_url_{i}",
                        )
                    track_inputs.append((t_name, t_desc, t_rules, t_url))

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

    parsed_tracks: list[HackathonTrack] = []
    if is_multi_track:
        for idx, (t_name, t_desc, t_rules, t_url) in enumerate(track_inputs):
            name_clean = t_name.strip()
            if name_clean:
                if t_url and t_url.strip():
                    try:
                        validate_public_url(t_url.strip())
                    except ResearchError as exc:
                        st.error(f"Track {idx+1} URL rejected: {exc}")
                        return
                parsed_tracks.append(
                    HackathonTrack(
                        name=name_clean,
                        description=t_desc.strip() or None,
                        track_rules=t_rules.strip() or None,
                        official_track_url=t_url.strip() or None,
                    )
                )
        if not parsed_tracks:
            st.error("Please provide at least one valid track with a name.")
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
        is_multi_track=is_multi_track,
        multi_track_mode=multi_track_mode,
        tracks=parsed_tracks,
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
        if is_multi_track:
            multi_result = pipeline.run_multi_track(hackathon, options)
            st.session_state["current_multi_result"] = multi_result
            st.session_state["current_session_id"] = multi_result.session_id
            winning_tid = (
                multi_result.comparison.overall_winning_track.id
                if (multi_result.comparison and multi_result.comparison.overall_winning_track)
                else (parsed_tracks[0].id if parsed_tracks else None)
            )
            best_track_res = multi_result.track_results.get(winning_tid) if winning_tid else None
            result = PipelineResult(
                session_id=multi_result.session_id,
                input=hackathon,
                intelligence=multi_result.shared_intelligence,
                domain_map=best_track_res.domain_map if best_track_res else None,
                innovation_report=best_track_res.innovation_report if best_track_res else None,
                feasibility=best_track_res.feasibility if best_track_res else None,
                debates=best_track_res.debates if best_track_res else [],
                winner=best_track_res.winner if best_track_res else None,
                report=multi_result.master_report,
                status=multi_result.status,
                started_at=multi_result.started_at,
                completed_at=multi_result.completed_at,
                duration_seconds=multi_result.duration_seconds,
            )
            st.session_state["current_result"] = result
        else:
            st.session_state["current_multi_result"] = None
            result = pipeline.run(hackathon, options)
            st.session_state["current_result"] = result
            st.session_state["current_session_id"] = result.session_id

    if result.status == "failed":
        st.error(f"Research failed: {result.error}")
        st.info(
            "The partial session is preserved in History. Common causes: Ollama "
            "stopped, model output repeatedly invalid, or a network outage."
        )
        return

    if is_multi_track and st.session_state.get("current_multi_result"):
        comp = st.session_state["current_multi_result"].comparison
        if comp and comp.overall_winning_candidate:
            st.success(
                f"Multi-track winner: {comp.overall_winning_candidate.candidate_title} "
                f"in track '{comp.overall_winning_track.name}' "
                f"({comp.overall_winning_candidate.total_score:.1f}/100)"
            )
        else:
            st.warning("Multi-track research finished. Check Results for per-track outcomes.")
    elif result.winner and result.winner.has_winner:
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
