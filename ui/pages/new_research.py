"""New hackathon research page with guided progressive disclosure workflow."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import streamlit as st

from config.settings import get_settings
from src.knowledge.document_intelligence.service import DocumentIntelligenceService
from src.models.hackathon import HackathonInput, HackathonTrack, MultiTrackMode
from src.models.pipeline import PipelineOptions, PipelineResult
from src.orchestration.pipeline import HackathonPipeline
from src.research.base import ResearchError, validate_public_url
from ui.components.common import (
    badge,
    format_datetime,
    get_llm,
    get_repository,
    hero,
    navigate_to,
    ollama_banner,
)


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
        "Configure Autonomous Hackathon Research",
        "Define your hackathon theme, target tracks, and constraints. Five specialized local agents "
        "will investigate organizers, discover domains, benchmark competitors, formulate architectures, "
        "and adversarially test candidate solutions.",
        eyebrow="Guided Research Builder",
        badge_text="Step-by-Step",
    )

    health = ollama_banner()
    model = health.get("active_model") or settings.ollama.model

    if auto_cfg:
        track_cnt = len(auto_cfg.tracks)
        track_info = f" ({track_cnt} dynamic tracks extracted)" if track_cnt else ""
        st.info(
            f"📁 **Document Ground Truth Active:** Pre-filled configuration from **{auto_cfg.name or 'Uploaded Rulebook'}**"
            f"{track_info}. All 5 agents cite active documents as unassailable evidence."
        )

    default_theme = auto_cfg.theme if auto_cfg else ""
    default_name = auto_cfg.name or "" if auto_cfg else ""
    default_website = (
        auto_cfg.website_url or ""
        if (auto_cfg and auto_cfg.website_url and not auto_cfg.website_url.startswith("doc://"))
        else ""
    )
    default_rules = (
        auto_cfg.rules_url or ""
        if (auto_cfg and auto_cfg.rules_url and not auto_cfg.rules_url.startswith("doc://"))
        else ""
    )
    default_constraints = auto_cfg.constraints or "" if auto_cfg else ""
    default_is_multi_track = auto_cfg.is_multi_track if auto_cfg else False
    default_mode_index = 1 if (auto_cfg and auto_cfg.multi_track_mode == MultiTrackMode.BEST_PER_TRACK) else 0
    default_num_tracks = len(auto_cfg.tracks) if (auto_cfg and auto_cfg.tracks) else 2
    default_has_deadline = bool(auto_cfg and auto_cfg.deadline)

    active_docs = repo.list_uploaded_documents(is_active_only=True)

    with st.form("research_configuration_form"):
        # 4-Step Progressive Tabs
        step1, step2, step3, step4 = st.tabs([
            "1 · Hackathon Brief",
            "2 · Tracks & Rules",
            "3 · Scope & Preferences",
            "4 · Review & Launch",
        ])

        # -------------------------------------------------------------
        # STEP 1: HACKATHON BRIEF
        # -------------------------------------------------------------
        with step1:
            st.markdown("#### Step 1: Hackathon Theme & Event Information")
            st.caption("Provide the primary theme or problem statement given by the organizers.")

            theme = st.text_area(
                "Hackathon Theme *",
                value=default_theme,
                placeholder="e.g. Sustainable Coastal Cities: AI, Climate Resilience & Disaster Management",
                height=90,
                help="The core prompt or theme provided by the hackathon organizers. Mandatory.",
            )

            c_n1, c_n2 = st.columns(2)
            with c_n1:
                name = st.text_input(
                    "Hackathon Name (optional)",
                    value=default_name,
                    placeholder="e.g. BeachHack Season 08",
                )
                website = st.text_input(
                    "Official Website URL (optional)",
                    value=default_website,
                    placeholder="https://beachhack.in",
                )
            with c_n2:
                rules = st.text_input(
                    "Rules / Guidelines URL (optional)",
                    value=default_rules,
                    placeholder="https://beachhack.in/guidelines",
                )
                constraints = st.text_input(
                    "General Constraints (optional)",
                    value=default_constraints,
                    placeholder="e.g. 36 hours build time, teams of 4, open source",
                )

            deadline_known = st.checkbox("I know the submission deadline", value=default_has_deadline)
            deadline: datetime | None = None
            if deadline_known:
                default_date = (
                    auto_cfg.deadline.date()
                    if (auto_cfg and auto_cfg.deadline)
                    else (date.today() + timedelta(days=2))
                )
                default_time = (
                    auto_cfg.deadline.time()
                    if (auto_cfg and auto_cfg.deadline)
                    else time(18, 0)
                )
                c_d1, c_d2 = st.columns(2)
                with c_d1:
                    chosen_date = st.date_input("Deadline Date", value=default_date)
                with c_d2:
                    chosen_time = st.time_input("Deadline Time (Local)", value=default_time)
                deadline = datetime.combine(chosen_date, chosen_time)

        # -------------------------------------------------------------
        # STEP 2: TRACKS & RULES
        # -------------------------------------------------------------
        with step2:
            st.markdown("#### Step 2: Track Architecture")
            st.caption("Choose between single-track focus or multi-track competitive exploration.")

            is_multi_track = st.checkbox(
                "Enable Multi-Track Research",
                value=default_is_multi_track,
                help="Evaluate multiple tracks independently and compare ideas across tracks.",
            )

            track_inputs: list[tuple[str, str, str, str]] = []
            multi_track_mode = MultiTrackMode.BEST_OVERALL

            if is_multi_track:
                st.markdown("##### Multi-Track Optimization Strategy")
                mode_choice = st.radio(
                    "Selection Mode",
                    [
                        "Mode A: Best Overall Track (Identify single strongest idea across all tracks)",
                        "Mode B: Best Idea Per Track (Identify strongest qualifying idea independently for every track)",
                    ],
                    index=default_mode_index,
                )
                multi_track_mode = (
                    MultiTrackMode.BEST_PER_TRACK
                    if "Mode B" in mode_choice
                    else MultiTrackMode.BEST_OVERALL
                )

                num_tracks = st.number_input(
                    "Number of Tracks", min_value=1, max_value=20, value=default_num_tracks, step=1
                )
                st.markdown("##### Define Track Details")

                for i in range(int(num_tracks)):
                    track_obj = auto_cfg.tracks[i] if (auto_cfg and i < len(auto_cfg.tracks)) else None
                    t_def_name = track_obj.name if track_obj else ""
                    t_def_desc = track_obj.description or "" if track_obj else ""
                    t_def_rules = track_obj.track_rules or "" if track_obj else ""
                    t_def_url = track_obj.official_track_url or "" if track_obj else ""

                    expander_label = f"Track {i+1}: {t_def_name}" if t_def_name else f"Track {i+1} Specifications"
                    with st.expander(expander_label, expanded=(i < 3)):
                        t_name = st.text_input(
                            f"Track {i+1} Name *",
                            value=t_def_name,
                            key=f"t_name_{i}",
                            placeholder=f"e.g. AI for Climate Resilience",
                        )
                        t_desc = st.text_area(
                            f"Track {i+1} Scope & Description (optional)",
                            value=t_def_desc,
                            key=f"t_desc_{i}",
                            height=65,
                        )
                        c_tr1, c_tr2 = st.columns(2)
                        with c_tr1:
                            t_rules = st.text_input(
                                f"Track {i+1} Specific Rules (optional)",
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
            else:
                st.info("Single-Track Mode: All five agents will focus deeply on the main theme provided in Step 1.")

        # -------------------------------------------------------------
        # STEP 3: SCOPE & PREFERENCES
        # -------------------------------------------------------------
        with step3:
            st.markdown("#### Step 3: Geographic Priority & Agent Tuning")
            st.caption("Ground research in real regional datasets, communities, and constraints.")

            g1, g2 = st.columns(2)
            with g1:
                geo_priority = st.selectbox(
                    "Geographical Research Focus",
                    [
                        "Kerala First (with Indian scalability and Global taxonomy)",
                        "India National (with Global benchmarking)",
                        "Global Broad (with Indian transferability)",
                    ],
                    index=0,
                )
            with g2:
                kerala_districts = st.multiselect(
                    "Target Kerala Districts (optional)",
                    [
                        "Alappuzha", "Ernakulam", "Idukki", "Kannur", "Kasaragod",
                        "Kollam", "Kottayam", "Kozhikode", "Malappuram", "Palakkad",
                        "Pathanamthitta", "Thiruvananthapuram", "Thrissur", "Wayanad",
                    ],
                    default=["Wayanad", "Alappuzha", "Palakkad", "Idukki"],
                )

            if active_docs:
                doc_tags = [f"`{d['filename']}`" for d in active_docs[:4]]
                st.markdown(
                    f"""
                    <div style="background: rgba(13, 148, 136, 0.08); border: 1px solid rgba(20, 184, 166, 0.25); border-radius: 8px; padding: 10px 14px; margin-top: 8px;">
                        <span style="color: #14b8a6; font-weight: 600;">📁 Ground Truth Active:</span>
                        <span style="color: #94a3b8; font-size: 0.9rem;"> {len(active_docs)} document(s) attached: {', '.join(doc_tags)}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.caption("💡 Tip: Upload official hackathon guidelines in the Document tab to automatically supply ground truth.")

            with st.expander("Advanced Pipeline Parameters (recommended defaults)"):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    max_domains = st.slider("Domains to Explore", 3, 20, settings.agent.max_domains)
                with c2:
                    per_domain = st.slider("Problems / Domain", 1, 5, settings.agent.problems_per_domain)
                with c3:
                    finalists = st.slider("Finalist Candidates", 2, 10, settings.agent.max_finalists)
                with c4:
                    rounds = st.slider("Debate Rounds", 1, 5, settings.agent.max_debate_rounds)
                include_ci = st.checkbox("Reuse stored Continuous Intelligence signals", value=True)

        # -------------------------------------------------------------
        # STEP 4: REVIEW & LAUNCH
        # -------------------------------------------------------------
        with step4:
            st.markdown("#### Step 4: Review Configuration & Launch Workflow")
            st.caption("Verify your research parameters before initiating autonomous local execution.")

            is_theme_valid = bool(theme and len(theme.strip()) >= 3)
            review_bg = "#111827" if is_theme_valid else "rgba(239, 68, 68, 0.08)"
            review_border = "rgba(148, 163, 184, 0.2)" if is_theme_valid else "rgba(239, 68, 68, 0.4)"

            track_summary = f"{len(track_inputs)} tracks configured" if is_multi_track else "Single unified track"
            mode_summary = (
                "Mode B: Independent Winner Per Track"
                if (is_multi_track and multi_track_mode == MultiTrackMode.BEST_PER_TRACK)
                else ("Mode A: Single Best Overall Track" if is_multi_track else "Single Track Deep Dive")
            )

            st.markdown(
                f"""
                <div style="background: {review_bg}; border: 1px solid {review_border}; border-radius: 12px; padding: 18px 22px; margin-bottom: 16px;">
                    <div style="font-size: 0.78rem; color: #14b8a6; text-transform: uppercase; font-weight: 700; margin-bottom: 6px;">
                        Execution Blueprint Summary
                    </div>
                    <div style="font-size: 1.15rem; font-weight: 600; color: #ffffff; margin-bottom: 8px;">
                        {theme if theme.strip() else '<span style=\"color:#f87171;\">[Theme is required]</span>'}
                    </div>
                    <div style="font-size: 0.88rem; color: #94a3b8; line-height: 1.6;">
                        <div>• <b>Event:</b> {name if name.strip() else 'General Hackathon'}</div>
                        <div>• <b>Track Architecture:</b> {track_summary} · {mode_summary}</div>
                        <div>• <b>Geographic Focus:</b> {geo_priority}</div>
                        <div>• <b>Inference Engine:</b> Local Ollama (`{model}`) · Zero Paid APIs</div>
                        <div>• <b>Document Evidence:</b> {len(active_docs)} active source document(s)</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            launch_btn = st.form_submit_button(
                "Launch Five-Agent Autonomous Research Workflow →",
                type="primary",
                use_container_width=True,
            )

    # If form has not been submitted, display helpful agent pipeline overview
    if not launch_btn:
        return

    # Validation Checks
    if not theme or len(theme.strip()) < 3:
        st.error("Please enter a valid hackathon theme of at least 3 characters.")
        return

    for label, url in (("Website", website), ("Rules", rules)):
        if url.strip():
            if url.strip().startswith("doc://"):
                st.error(f"{label} URL cannot be an internal document reference ('doc://'). Uploaded documents are automatically used as primary evidence.")
                return
            try:
                validate_public_url(url.strip())
            except ResearchError as exc:
                st.error(f"{label} URL rejected: {exc}")
                return

    if not health.get("available"):
        st.error("Ollama is offline. Start the Ollama server before running research.")
        return
    if not health.get("models"):
        st.error("No Ollama model is installed. Open Settings → Model to download one.")
        return

    parsed_tracks: list[HackathonTrack] = []
    if is_multi_track:
        for idx, (t_name, t_desc, t_rules, t_url) in enumerate(track_inputs):
            name_clean = t_name.strip()
            if name_clean:
                clean_url = t_url.strip() if t_url else None
                if clean_url:
                    if clean_url.startswith("doc://"):
                        st.error(f"Track {idx+1} URL cannot be an internal document reference ('doc://'). Uploaded documents are automatically used as primary evidence.")
                        return
                    try:
                        validate_public_url(clean_url)
                    except ResearchError as exc:
                        st.error(f"Track {idx+1} URL rejected: {exc}")
                        return
                parsed_tracks.append(
                    HackathonTrack(
                        name=name_clean,
                        description=t_desc.strip() or None,
                        track_rules=t_rules.strip() or None,
                        official_track_url=clean_url or None,
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

    # Initialize live telemetry state
    st.session_state["research_in_progress"] = True
    st.session_state["live_events"] = []
    st.session_state["active_agent_name"] = "Hackathon Intelligence"
    st.session_state["active_progress_fraction"] = 0.05

    progress = st.progress(0.0)
    status = st.empty()
    log = st.expander("Live Agent Deliberation Log", expanded=True)

    def on_progress(stage: str, message: str, fraction: float) -> None:
        fraction_bounded = min(max(fraction, 0.0), 1.0)
        progress.progress(fraction_bounded)
        status.markdown(f"**{fraction_bounded:.0%}** · `{stage}`: {message}")
        event = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "stage": stage,
            "message": message,
        }
        st.session_state["live_events"].append(event)
        st.session_state["active_agent_name"] = stage
        st.session_state["active_progress_fraction"] = fraction_bounded
        recent_msgs = [
            f"`[{e['timestamp']}]` **{e['stage']}**: {e['message']}"
            for e in st.session_state["live_events"][-8:]
        ]
        log.markdown("\n\n".join(recent_msgs))

    pipeline = HackathonPipeline(
        llm=get_llm(),
        repository=repo,
        progress=on_progress,
    )

    with st.spinner("Autonomous agents are conducting research and debate. Do not close this tab."):
        try:
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
        finally:
            st.session_state["research_in_progress"] = False

    if result.status == "failed":
        st.error(f"Research execution failed: {result.error}")
        return

    st.success("Research workflow completed successfully! Redirecting to Results...")
    navigate_to("Results & Comparisons")
