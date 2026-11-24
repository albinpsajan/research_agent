"""Page One — New Research: Guided ChatGPT-style research builder, live execution, and embedded results."""

from __future__ import annotations

import hashlib

import streamlit as st

from config.settings import get_settings
from src.knowledge.document_intelligence.service import DocumentIntelligenceService
from src.models.hackathon import HackathonInput, HackathonTrack, MultiTrackMode
from src.models.pipeline import PipelineOptions, PipelineResult
from src.orchestration.loader import load_multi_track_result, load_session_result
from src.orchestration.pipeline import HackathonPipeline
from src.research.base import ResearchError, validate_public_url
from ui.components.common import (
    format_datetime,
    get_llm,
    get_repository,
    hero,
    ollama_banner,
)
from ui.pages import results as results_page


def render() -> None:
    settings = get_settings()
    repo = get_repository()
    llm = get_llm()
    service = DocumentIntelligenceService(repository=repo, llm=llm)

    # -------------------------------------------------------------------------
    # 0. Handle sidebar session loading request
    # -------------------------------------------------------------------------
    from unittest.mock import MagicMock

    if (
        "target_session_to_load" in st.session_state
        and st.session_state["target_session_to_load"]
        and not isinstance(st.session_state["target_session_to_load"], MagicMock)
    ):
        sess_id = st.session_state.pop("target_session_to_load")
        _load_session_into_state(sess_id, repo)
        st.session_state["view_mode"] = "results"
        st.rerun()

    # -------------------------------------------------------------------------
    # 1. If viewing results or previous research is loaded
    # -------------------------------------------------------------------------
    has_results = bool(
        (st.session_state.get("current_result") and not isinstance(st.session_state.get("current_result"), MagicMock))
        or (st.session_state.get("current_multi_result") and not isinstance(st.session_state.get("current_multi_result"), MagicMock))
    )
    if has_results and st.session_state.get("view_mode") == "results":
        col_back, _ = st.columns([1, 4])
        with col_back:
            if st.button("← Start New Research", type="secondary", use_container_width=True):
                st.session_state["current_result"] = None
                st.session_state["current_multi_result"] = None
                st.session_state["configured_hackathon"] = None
                st.session_state["view_mode"] = "builder"
                st.rerun()

        results_page.render()
        return

    # -------------------------------------------------------------------------
    # 2. If research is currently in progress
    # -------------------------------------------------------------------------
    if st.session_state.get("research_in_progress") is True:
        _render_execution_progress()
        return

    # -------------------------------------------------------------------------
    # 3. New Research Builder: ChatGPT-style Welcome & Input
    # -------------------------------------------------------------------------
    hero(
        "HackathonIQ",
        "Evidence over ideas. Upload your hackathon documents or describe your challenge to discover the strongest hackathon-ready solutions.",
        eyebrow="Evidence Over Ideas",
        badge_text="Autonomous Engine",
    )

    health = ollama_banner()
    model = health.get("active_model") or settings.ollama.model

    # Check for active document auto-configuration
    auto_cfg: HackathonInput | None = st.session_state.get("configured_hackathon")
    if not auto_cfg:
        auto_cfg = service.get_active_auto_configuration()
        if auto_cfg:
            st.session_state["configured_hackathon"] = auto_cfg

    # Mode selection: Document Upload vs Manual Entry
    tab_doc, tab_manual = st.tabs([
        "📁 Upload Documents (PDF, Rulebooks, Posters)",
        "✍ Enter Details Manually",
    ])

    # -------------------------------------------------------------
    # TAB A: DOCUMENT UPLOAD & AUTO-EXTRACTION (Option A)
    # -------------------------------------------------------------
    with tab_doc:
        st.markdown("#### Upload Event Guidelines or Problem Briefs")
        st.caption("Supports PDF, scanned documents, JPG, PNG, WEBP. You can upload multiple files.")

        uploaded_files = st.file_uploader(
            "Drop hackathon documents here",
            type=["pdf", "jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key="doc_uploader_main",
            label_visibility="collapsed",
        )

        if uploaded_files and not isinstance(uploaded_files, MagicMock):
            # Check if any new files need extraction
            new_files_to_process = []
            for f in uploaded_files:
                f_bytes = f.getvalue()
                f_hash = hashlib.sha256(f_bytes).hexdigest()
                existing_doc = repo.get_uploaded_document_by_hash(f_hash)
                if not existing_doc:
                    new_files_to_process.append((f, f_bytes))

            if new_files_to_process:
                st.info(f"Processing {len(new_files_to_process)} uploaded document(s)...")
                p_bar = st.progress(0.0)
                for idx, (f, bts) in enumerate(new_files_to_process):
                    try:
                        service.upload_document(
                            filename=f.name,
                            file_bytes=bts,
                            extract_structured=True,
                        )
                    except Exception as e:
                        st.error(f"Error processing {f.name}: {e}")
                    p_bar.progress((idx + 1) / len(new_files_to_process))

                # Auto-configure event details from extracted documents
                extracted_input, status, conflicts, profile = service.auto_configure_hackathon(
                    mode=MultiTrackMode.BEST_OVERALL
                )
                if extracted_input:
                    st.session_state["configured_hackathon"] = extracted_input
                    auto_cfg = extracted_input
                st.success("✓ Documents ingested and analyzed! Review and edit the extracted details below.")
                st.rerun()

    # Determine default field values (from extracted document or manual state)
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
    default_mode_idx = 1 if (auto_cfg and auto_cfg.multi_track_mode == MultiTrackMode.BEST_PER_TRACK) else 0
    default_tracks = auto_cfg.tracks if (auto_cfg and auto_cfg.tracks) else []

    # -------------------------------------------------------------
    # EDITABLE RESEARCH CONFIGURATION FORM
    # -------------------------------------------------------------
    with tab_manual:
        st.markdown("#### Enter or Edit Hackathon Parameters")

    if auto_cfg:
        track_info = f" ({len(default_tracks)} tracks detected)" if default_tracks else ""
        st.markdown(
            f"""
            <div style="background: rgba(13, 148, 136, 0.08); border: 1px solid rgba(20, 184, 166, 0.25); border-radius: 8px; padding: 10px 16px; margin: 12px 0;">
                <span style="color: #14b8a6; font-weight: 600;">📁 Ground Truth Active:</span>
                <span style="color: #cbd5e1; font-size: 0.92rem;"> Pre-filled from <b>{auto_cfg.name or 'Uploaded Document'}</b>{track_info}. You can review and edit any value.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Initialize dynamic tracks in session state if not present
    if "builder_tracks" not in st.session_state or auto_cfg:
        st.session_state["builder_tracks"] = [
            {
                "name": t.name,
                "description": t.description or "",
                "track_rules": t.track_rules or "",
                "official_track_url": t.official_track_url or "",
            }
            for t in default_tracks
        ]

    # Form inputs
    theme = st.text_area(
        "Hackathon Theme *",
        value=default_theme,
        placeholder="e.g. Sustainable Coastal Cities: AI, Climate Resilience & Disaster Management",
        height=85,
        help="The core challenge or theme of the hackathon. Required.",
    )

    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Hackathon Name (optional)", value=default_name, placeholder="e.g. BeachHack Season 08")
        website = st.text_input("Official Website (optional)", value=default_website, placeholder="https://beachhack.in")
    with c2:
        rules = st.text_input("Rules URL (optional)", value=default_rules, placeholder="https://beachhack.in/rules")
        constraints = st.text_input(
            "Constraints (optional)",
            value=default_constraints,
            placeholder="e.g. 36 hours build time, teams of 4",
        )

    # Track Configuration
    st.markdown("##### Track Architecture")
    is_multi_track = st.checkbox(
        "Multi-Track Hackathon",
        value=default_is_multi_track or len(st.session_state["builder_tracks"]) > 1,
        help="Enable to evaluate multiple distinct problem tracks independently.",
    )

    multi_track_mode = MultiTrackMode.BEST_OVERALL
    if is_multi_track:
        mode_choice = st.radio(
            "Optimization Mode",
            [
                "Mode A: Best Overall Track (Find single strongest opportunity across all tracks)",
                "Mode B: Best Idea Per Track (Find the strongest qualifying idea independently for every track)",
            ],
            index=default_mode_idx,
            horizontal=True,
        )
        multi_track_mode = (
            MultiTrackMode.BEST_PER_TRACK if "Mode B" in mode_choice else MultiTrackMode.BEST_OVERALL
        )

        st.caption("Tracks detected from documents or added manually:")
        tracks_list = st.session_state.get("builder_tracks", [])

        # Display track editor cards
        updated_tracks = []
        for i, trk in enumerate(tracks_list):
            with st.expander(f"Track {i+1}: {trk.get('name') or 'Unnamed Track'}", expanded=(i < 3)):
                t_name = st.text_input(f"Track {i+1} Name *", value=trk.get("name", ""), key=f"tr_name_{i}")
                t_desc = st.text_area(f"Track {i+1} Description (optional)", value=trk.get("description", ""), key=f"tr_desc_{i}", height=55)
                c_tr1, c_tr2 = st.columns(2)
                with c_tr1:
                    t_rules = st.text_input(f"Track {i+1} Rules (optional)", value=trk.get("track_rules", ""), key=f"tr_rules_{i}")
                with c_tr2:
                    t_url = st.text_input(f"Track {i+1} Official URL (optional)", value=trk.get("official_track_url", ""), key=f"tr_url_{i}")
                updated_tracks.append({
                    "name": t_name,
                    "description": t_desc,
                    "track_rules": t_rules,
                    "official_track_url": t_url,
                })
        st.session_state["builder_tracks"] = updated_tracks

        col_t_add, col_t_rm = st.columns([1, 1])
        with col_t_add:
            if st.button("+ Add Another Track", type="secondary"):
                st.session_state["builder_tracks"].append({"name": "", "description": "", "track_rules": "", "official_track_url": ""})
                st.rerun()
        with col_t_rm:
            if len(st.session_state["builder_tracks"]) > 1 and st.button("- Remove Last Track", type="secondary"):
                st.session_state["builder_tracks"].pop()
                st.rerun()

    # Scope & Regional Focus
    st.markdown("##### Research Scope & Regional Focus")
    c_geo1, c_geo2 = st.columns([2, 1])
    with c_geo1:
        geo_priority = st.selectbox(
            "Geographical Research Focus",
            [
                "Kerala First (with Indian scalability and Global taxonomy)",
                "India National (with Global benchmarking)",
                "Global Broad (with Indian transferability)",
            ],
            index=0,
        )
    with c_geo2:
        kerala_districts = st.multiselect(
            "Kerala Districts",
            [
                "Alappuzha", "Ernakulam", "Idukki", "Kannur", "Kasaragod",
                "Kollam", "Kottayam", "Kozhikode", "Malappuram", "Palakkad",
                "Pathanamthitta", "Thiruvananthapuram", "Thrissur", "Wayanad",
            ],
            default=["Wayanad", "Alappuzha", "Palakkad"],
        )

    # -------------------------------------------------------------
    # DUPLICATE DETECTION BEFORE LAUNCH
    # -------------------------------------------------------------
    duplicate_session = None
    if theme.strip():
        duplicate_session = repo.find_session_by_theme_or_name(theme, name)

    if duplicate_session:
        d_id = duplicate_session["id"]
        d_name = duplicate_session.get("hackathon_name") or duplicate_session.get("hackathon_theme")
        d_date = format_datetime(duplicate_session.get("created_at"))
        st.warning(
            f"⚠️ **Existing Research Detected:** A research run for **'{d_name}'** already exists (Session `{d_id[:8]}`, created {d_date}). "
            "You can load previous results instantly or start a fresh run."
        )
        col_dup1, col_dup2 = st.columns([1, 2])
        with col_dup1:
            if st.button("Load Existing Results", key=f"dup_load_{d_id}", type="primary", use_container_width=True):
                _load_session_into_state(d_id, repo)
                st.session_state["view_mode"] = "results"
                st.rerun()

    # -------------------------------------------------------------
    # PRE-FLIGHT REVIEW SUMMARY
    # -------------------------------------------------------------
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    active_docs = repo.list_uploaded_documents(is_active_only=True)

    tracks_to_run = [
        HackathonTrack(
            name=t["name"].strip(),
            description=t["description"].strip() or None,
            track_rules=t["track_rules"].strip() or None,
            official_track_url=t["official_track_url"].strip() or None,
        )
        for t in st.session_state.get("builder_tracks", [])
        if t.get("name", "").strip()
    ] if is_multi_track else []

    track_summary_text = (
        f"{len(tracks_to_run)} tracks · {'Mode B: Best Idea Per Track' if multi_track_mode == MultiTrackMode.BEST_PER_TRACK else 'Mode A: Best Overall Track'}"
        if is_multi_track
        else "Single Unified Track"
    )

    # -------------------------------------------------------------
    # START RESEARCH FORM (Explicit User Confirmation)
    # -------------------------------------------------------------
    with st.form("research_execution_form"):
        st.markdown(
            f"""
            <div style="background: #111827; border: 1px solid rgba(148, 163, 184, 0.16); border-radius: 10px; padding: 16px 20px; margin-bottom: 16px;">
                <div style="color: #14b8a6; font-size: 0.75rem; text-transform: uppercase; font-weight: 700; letter-spacing: 0.08em; margin-bottom: 4px;">
                    Review Configuration Before Launch
                </div>
                <div style="font-weight: 600; color: #f8fafc; font-size: 1.05rem; margin-bottom: 6px;">
                    {theme if theme.strip() else '<span style="color:#f87171;">[Theme is required to start]</span>'}
                </div>
                <div style="color: #94a3b8; font-size: 0.88rem; line-height: 1.6;">
                    • <b>Event:</b> {name if name.strip() else 'General Hackathon'}<br>
                    • <b>Track Architecture:</b> {track_summary_text}<br>
                    • <b>Geographic Focus:</b> {geo_priority}<br>
                    • <b>Ground Truth Documents:</b> {len(active_docs)} document(s) attached
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        start_clicked = st.form_submit_button("Start Research →", type="primary", use_container_width=True)

    if not start_clicked:
        return

    # Validation
    if not theme or len(theme.strip()) < 3:
        st.error("Please enter a hackathon theme of at least 3 characters.")
        return

    if is_multi_track and not tracks_to_run:
        st.error("Please provide at least one valid track with a name for multi-track research.")
        return

    for label, url_val in (("Website", website), ("Rules", rules)):
        if url_val.strip() and not url_val.strip().startswith("doc://"):
            try:
                validate_public_url(url_val.strip())
            except ResearchError as exc:
                st.error(f"{label} URL rejected: {exc}")
                return

    # Prepare inputs
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
        constraints=combined_constraints,
        is_multi_track=is_multi_track,
        multi_track_mode=multi_track_mode,
        tracks=tracks_to_run,
    )
    options = PipelineOptions(
        max_domains=settings.agent.max_domains,
        problems_per_domain=settings.agent.problems_per_domain,
        max_finalists=settings.agent.max_finalists,
        max_debate_rounds=settings.agent.max_debate_rounds,
    )

    # Launch execution with live progress inside New Research
    st.session_state["research_in_progress"] = True
    st.session_state["current_theme_running"] = theme.strip()
    st.session_state["current_name_running"] = name.strip() or "Hackathon"
    st.session_state["execution_stage"] = "Analyzing Hackathon Ground Truth & Rules"
    st.session_state["execution_progress"] = 0.05
    st.session_state["execution_message"] = "Reading official event rules and extracting judging criteria..."

    _execute_research_pipeline(hackathon, options, repo, llm)


def _execute_research_pipeline(hackathon: HackathonInput, options: PipelineOptions, repo, llm) -> None:
    """Executes the pipeline with user-friendly live stage tracking."""
    progress_bar = st.progress(0.0)
    status_text = st.empty()

    stage_names = {
        "intelligence": "1. Analyzing Hackathon Ground Truth & Rules",
        "domain": "2. Dynamic Domain & Problem Discovery",
        "innovation": "3. Competitor Investigation & Benchmarking",
        "architect": "4. Solution Architecture & Feasibility",
        "critic": "5. Quality Gate Evaluation & Debate",
    }

    def on_progress(stage: str, message: str, frac: float) -> None:
        frac_bounded = min(max(frac, 0.0), 1.0)
        progress_bar.progress(frac_bounded)
        clean_stage = stage_names.get(stage.lower(), stage)
        status_text.markdown(f"**{frac_bounded:.0%}** · `{clean_stage}` — {message}")
        st.session_state["execution_progress"] = frac_bounded
        st.session_state["execution_stage"] = clean_stage
        st.session_state["execution_message"] = message

    pipeline = HackathonPipeline(llm=llm, repository=repo, progress=on_progress)

    try:
        with st.spinner("Autonomous agents are conducting research, testing competitors, and debating ideas..."):
            if hackathon.is_multi_track:
                multi_res = pipeline.run_multi_track(hackathon, options)
                st.session_state["current_multi_result"] = multi_res
                st.session_state["current_session_id"] = multi_res.session_id
                comp = multi_res.comparison
                winning_tid = comp.overall_winning_track.id if (comp and comp.overall_winning_track) else None
                best_track_res = multi_res.track_results.get(winning_tid) if winning_tid else None
                result = PipelineResult(
                    session_id=multi_res.session_id,
                    input=hackathon,
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
                st.session_state["current_result"] = result
            else:
                st.session_state["current_multi_result"] = None
                result = pipeline.run(hackathon, options)
                st.session_state["current_result"] = result
                st.session_state["current_session_id"] = result.session_id

        st.session_state["research_in_progress"] = False
        st.session_state["view_mode"] = "results"
        st.success("Research completed successfully!")
        st.rerun()

    except Exception as exc:  # noqa: BLE001
        st.session_state["research_in_progress"] = False
        st.error(f"Research execution failed: {exc}")


def _render_execution_progress() -> None:
    """Renders clean user-facing progress without developer logs."""
    theme = st.session_state.get("current_theme_running", "Hackathon Research")
    name = st.session_state.get("current_name_running", "Hackathon")
    stage = st.session_state.get("execution_stage", "Executing autonomous research...")
    message = st.session_state.get("execution_message", "Agents are evaluating problem candidates...")
    progress_val = float(st.session_state.get("execution_progress", 0.1))

    hero(
        theme,
        f"{name} · Autonomous Research in Progress",
        eyebrow="Live Research Progress",
        badge_text="Executing",
    )

    st.progress(min(max(progress_val, 0.0), 1.0))
    st.markdown(f"**Current Stage:** `{stage}`")
    st.caption(f"Activity: {message}")

    st.markdown(
        """
        <div style="background: #111827; border: 1px solid rgba(148, 163, 184, 0.12); border-radius: 10px; padding: 18px 22px; margin-top: 18px;">
            <div style="color: #14b8a6; font-weight: 600; font-size: 0.95rem; margin-bottom: 6px;">
                Autonomous 5-Stage Deliberation Pipeline:
            </div>
            <div style="color: #94a3b8; font-size: 0.88rem; line-height: 1.6;">
                1. <b>Ground Truth Analysis</b>: Rules, constraints, judging criteria<br>
                2. <b>Dynamic Domain Discovery</b>: Uncovering underserved real-world problems<br>
                3. <b>Competitor Research</b>: Auditing GitHub, arXiv, and existing startups<br>
                4. <b>Solution Architecture</b>: Formulating buildable architectures and demo plans<br>
                5. <b>Adversarial Quality Gates</b>: 10-gate audit and honest winner selection
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _load_session_into_state(session_id: str, repository) -> None:
    """Helper to populate session state with persisted result."""
    session = repository.get_session(session_id)
    if session and session.get("is_multi_track"):
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
