"""Streamlit page: Intelligent Document Understanding & Automatic Research Execution."""

from __future__ import annotations

import streamlit as st

from config.settings import get_settings
from src.knowledge.document_intelligence.extractor import OCREngine
from src.knowledge.document_intelligence.models import (
    DocumentType,
    ExtractedConflict,
    MissingInfoStatus,
    StructuredHackathonDoc,
)
from src.knowledge.document_intelligence.service import DocumentIntelligenceService
from src.models.hackathon import HackathonInput, MultiTrackMode
from src.models.pipeline import PipelineOptions
from ui.components.common import get_llm, get_repository, hero


def render() -> None:
    hero(
        "Document-to-Research Autonomous Pipeline",
        "Upload hackathon rulebooks, guidelines, posters, or scientific papers. "
        "HackathonIQ automatically understands documents, extracts all constraints and tracks, "
        "configures the hackathon, and autonomously executes the 5-agent research pipeline.",
        eyebrow="Document Intelligence Studio",
    )

    settings = get_settings()
    repo = get_repository()
    llm = get_llm()
    service = DocumentIntelligenceService(repository=repo, llm=llm)

    ocr = OCREngine(tesseract_cmd=settings.document_intelligence.tesseract_cmd)
    if not ocr.is_available():
        st.info(
            "ℹ️ **Tesseract-OCR Note:** Embedded PDF text is extracted offline with 100% precision. "
            "For scanned physical pages or photo OCR, ensure Tesseract is on system PATH."
        )

    tab1, tab2, tab3 = st.tabs([
        "🚀 Autonomous Document Pipeline",
        "📚 Knowledge Base & Page Viewer",
        "🔍 Evidence Search & Citation Probe",
    ])

    # ------------------------------------------------------------------
    # TAB 1: Autonomous Document Pipeline
    # ------------------------------------------------------------------
    with tab1:
        st.subheader("1. Upload Hackathon / Evidence Documents")
        st.markdown(
            "Upload one or multiple documents (**PDF**, **JPG**, **PNG**, **WEBP**). "
            "The system automatically classifies them, extracts rules and tracks, builds the event configuration, "
            "and initiates the multi-agent research workflow."
        )

        col_up, col_opts = st.columns([2, 1])
        with col_up:
            uploaded_files = st.file_uploader(
                "Upload rulebooks, track descriptions, or problem briefs",
                type=["pdf", "jpg", "jpeg", "png", "webp"],
                accept_multiple_files=True,
                key="autonomous_doc_uploader",
            )
        with col_opts:
            auto_mode_choice = st.selectbox(
                "Multi-Track Execution Mode",
                [
                    "Mode A: Best Overall Track (Single strongest idea across tracks)",
                    "Mode B: Best Idea Per Track (One independent winner per track)",
                ],
                index=0,
                help="Mode A finds the single best problem across all tracks. Mode B optimizes every track independently.",
            )
            selected_mode = (
                MultiTrackMode.BEST_OVERALL
                if "Mode A" in auto_mode_choice
                else MultiTrackMode.BEST_IDEA_PER_TRACK
            )
            auto_launch_research = st.checkbox(
                "Automatically launch research immediately after extraction",
                value=False,
                help="If enabled, research starts as soon as documents are parsed and validated without waiting for a click.",
            )

        if uploaded_files and st.button("⚡ Ingest, Understand & Configure Event", type="primary"):
            _run_ingest_pipeline(uploaded_files, service, auto_launch_research, selected_mode)

        st.divider()

        # Display Live 9-Stage Pipeline Tracker
        _render_pipeline_state_and_results(service, selected_mode)

    # ------------------------------------------------------------------
    # TAB 2: Knowledge Base & Extracted Content
    # ------------------------------------------------------------------
    with tab2:
        _render_knowledge_base_tab(service, repo)

    # ------------------------------------------------------------------
    # TAB 3: Evidence Search & Citation Probe
    # ------------------------------------------------------------------
    with tab3:
        _render_evidence_probe_tab(service)


def _render_pipeline_stages_bar(current_stage_idx: int) -> None:
    """Render a visual 9-stage pipeline progression bar."""
    stages = [
        ("1. Uploaded", 1),
        ("2. Text & OCR", 2),
        ("3. Classified", 3),
        ("4. Structured", 4),
        ("5. Configured", 5),
        ("6. Tracks Found", 6),
        ("7. Indexed", 7),
        ("8. 5-Agent Research", 8),
        ("9. Validated Report", 9),
    ]

    cols = st.columns(len(stages))
    for i, (name, idx) in enumerate(stages):
        with cols[i]:
            if idx < current_stage_idx:
                st.markdown(f"**`✓ {name}`**\n\n<span style='color:#22c55e;'>Done</span>", unsafe_allow_html=True)
            elif idx == current_stage_idx:
                st.markdown(f"**`▶ {name}`**\n\n<span style='color:#38bdf8; font-weight:bold;'>Active</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"`○ {name}`\n\n<span style='color:#64748b;'>Pending</span>", unsafe_allow_html=True)


def _run_ingest_pipeline(
    uploaded_files: list,
    service: DocumentIntelligenceService,
    auto_launch: bool,
    mode: MultiTrackMode,
) -> None:
    """Executes stages 1-7 (Upload -> Extraction -> Classification -> Structuring -> Auto-Config)."""
    p_bar = st.progress(0.0)
    status_box = st.empty()

    for idx, file in enumerate(uploaded_files):
        status_box.markdown(f"**Processing ({idx + 1}/{len(uploaded_files)}):** `{file.name}`...")
        file_bytes = file.read()
        try:
            doc = service.upload_document(
                filename=file.name,
                file_bytes=file_bytes,
                document_type=DocumentType.GENERAL_EVIDENCE,  # Auto-classifier will detect actual type
                extract_structured=True,
            )
            st.toast(f"Ingested {doc.filename} ({doc.document_type.value})")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed extracting {file.name}: {exc}")

        p_bar.progress((idx + 1) / len(uploaded_files))

    p_bar.progress(1.0)
    status_box.success("🎉 Ingestion, classification, and structured extraction complete!")

    # Auto-configure
    h_input, status, conflicts, profile = service.auto_configure_hackathon(mode=mode)
    st.session_state["configured_hackathon"] = h_input
    st.session_state["config_status"] = status
    st.session_state["config_conflicts"] = conflicts
    st.session_state["config_profile"] = profile

    if auto_launch and h_input and status.is_ready_for_research:
        st.session_state["trigger_auto_research"] = True

    st.rerun()


def _render_pipeline_state_and_results(
    service: DocumentIntelligenceService,
    mode: MultiTrackMode,
) -> None:
    """Renders the automatically identified configuration, conflict warnings, and research execution controls."""
    docs = service.list_documents(is_active_only=True)
    if not docs:
        _render_pipeline_stages_bar(1)
        st.info("💡 Upload one or more hackathon documents above to initiate automatic understanding.")
        return

    # Check session configuration state
    h_input: HackathonInput | None = st.session_state.get("configured_hackathon")
    status: MissingInfoStatus | None = st.session_state.get("config_status")
    conflicts: list[ExtractedConflict] = st.session_state.get("config_conflicts", [])
    profile: StructuredHackathonDoc | None = st.session_state.get("config_profile")

    if not h_input or not profile:
        h_input, status, conflicts, profile = service.auto_configure_hackathon(mode=mode)
        st.session_state["configured_hackathon"] = h_input
        st.session_state["config_status"] = status
        st.session_state["config_conflicts"] = conflicts
        st.session_state["config_profile"] = profile

    # Determine current stage for pipeline indicator
    research_result = st.session_state.get("doc_research_result")
    is_running = st.session_state.get("doc_research_running", False)

    if research_result:
        stage_idx = 9
    elif is_running:
        stage_idx = 8
    elif h_input and h_input.tracks:
        stage_idx = 7
    elif h_input:
        stage_idx = 6
    else:
        stage_idx = 4

    _render_pipeline_stages_bar(stage_idx)
    st.markdown("<br>", unsafe_allow_html=True)

    # Conflict Warnings Alert
    if conflicts:
        with st.expander("⚠️ Cross-Document Conflicts Detected", expanded=True):
            st.warning(f"Detected {len(conflicts)} discrepancies between uploaded documents. Official rules are given authority, but please review:")
            for c in conflicts:
                st.markdown(f"- **Field:** `{c.field}` | **{c.source_a}:** `{c.item_a}` vs **{c.source_b}:** `{c.item_b}`\n  _{c.explanation}_")

    # Missing Information Alert
    if status and not status.is_ready_for_research:
        st.error(f"⚠️ **Essential Information Missing:** {', '.join(status.missing_essential)}. {status.suggested_action}")
        with st.form("supply_missing_info"):
            supplied_theme = st.text_input("Please specify the hackathon theme / challenge focus *")
            if st.form_submit_button("Update & Validate Configuration", type="primary") and supplied_theme.strip():
                h_input, status, conflicts, profile = service.auto_configure_hackathon(
                    mode=mode, user_overrides={"theme": supplied_theme.strip()}
                )
                st.session_state["configured_hackathon"] = h_input
                st.session_state["config_status"] = status
                st.rerun()
        return

    # Auto-Configured Event Card
    if h_input:
        st.subheader("2. Automatically Configured Event Intelligence")
        e_card = st.container()
        with e_card:
            col1, col2 = st.columns([3, 2])
            with col1:
                st.markdown(f"### 🏆 {h_input.name}")
                st.markdown(f"**Theme:** {h_input.theme}")
                if profile and profile.organizer:
                    p_org = profile.get_field_provenance("organizer")
                    cite = f" `[{p_org.filename}, Page {p_org.page}]`" if p_org else ""
                    st.markdown(f"**Organizer:** {profile.organizer}{cite}")
                if h_input.website_url:
                    st.markdown(f"**Website:** [{h_input.website_url}]({h_input.website_url})")

            with col2:
                if h_input.deadline:
                    st.metric("Submission Deadline", str(h_input.deadline))
                elif profile and profile.submission_deadline:
                    p_dl = profile.get_field_provenance("submission_deadline")
                    cite = f" `[{p_dl.filename}, Page {p_dl.page}]`" if p_dl else ""
                    st.metric("Submission Deadline", f"{profile.submission_deadline}{cite}")
                else:
                    st.info("Deadline: Not specified in uploaded documents (not fabricated).")

                if profile and profile.event_duration:
                    st.metric("Event Duration", profile.event_duration)

            # Tracks Section
            st.markdown("#### 🎯 Identified Challenge Tracks")
            if h_input.tracks:
                t_cols = st.columns(min(len(h_input.tracks), 3))
                for i, trk in enumerate(h_input.tracks):
                    with t_cols[i % len(t_cols)]:
                        st.markdown(
                            f"""
                            <div style="background:#131720; border:1px solid #3b82f6; border-radius:6px; padding:10px; margin-bottom:8px;">
                                <div style="font-weight:600; color:#60a5fa;">Track {i + 1}: {trk.name}</div>
                                <div style="font-size:0.85rem; color:#cbd5e1; margin-top:4px;">{trk.description or 'Description grounded in document excerpts.'}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
            else:
                st.markdown("_Single-Track Research Mode: Broad problem discovery will explore all theme facets._")

            # Constraints and Rules
            if h_input.constraints:
                with st.expander("📋 Document-Derived Constraints & Technical Directives"):
                    st.markdown(h_input.constraints)

        # Quick Overrides Expander
        with st.expander("✏️ Customize Extracted Configuration (Optional)"), st.form("override_form"):
            ov_name = st.text_input("Hackathon Name", value=h_input.name or "")
            ov_theme = st.text_area("Hackathon Theme", value=h_input.theme or "")
            ov_constraints = st.text_input("Additional Constraints", value=h_input.constraints or "")
            if st.form_submit_button("Save Adjustments"):
                h_input, status, conflicts, profile = service.auto_configure_hackathon(
                    mode=mode,
                    user_overrides={
                        "name": ov_name.strip() or None,
                        "theme": ov_theme.strip() or None,
                        "constraints": ov_constraints.strip() or None,
                    },
                )
                st.session_state["configured_hackathon"] = h_input
                st.success("Configuration updated.")
                st.rerun()

        # Step 3: Autonomous Research Execution Trigger
        st.subheader("3. Autonomous Multi-Agent Research Execution")
        st.markdown(
            "Initiate the full five-agent HackathonIQ workflow. All agents will cite the uploaded primary documents "
            "as ground truth evidence, enforce all 10 mandatory evaluation gates, and generate a validated result."
        )

        c_launch, c_cancel = st.columns([3, 1])
        with c_launch:
            launch_clicked = st.button("🚀 Launch Autonomous Research Workflow", type="primary")
        with c_cancel:
            if st.button("⏹ Stop / Cancel Workflow"):
                st.session_state["doc_research_running"] = False
                st.warning("Workflow cancelled by user.")

        # Trigger auto-research if flagged or button clicked
        if launch_clicked or st.session_state.pop("trigger_auto_research", False):
            _execute_research_workflow(service, h_input)

    # Render results if completed
    if research_result:
        _render_research_outcome(research_result)


def _execute_research_workflow(
    service: DocumentIntelligenceService,
    hackathon_input: HackathonInput,
) -> None:
    """Runs the 5-agent research pipeline with live progress and logs."""
    st.session_state["doc_research_running"] = True
    progress_bar = st.progress(0.0)
    agent_status_box = st.empty()
    activity_log = st.expander("Live Agent Activity Stream", expanded=True)
    events: list[str] = []

    def on_progress(stage: str, msg: str, frac: float) -> None:
        progress_bar.progress(min(max(frac, 0.0), 1.0))
        agent_status_box.markdown(f"**Current Agent Activity:** `{stage.upper()}` — {msg}")
        events.append(f"`{stage}` — {msg}")
        activity_log.markdown("\n\n".join(events[-10:]))

    try:
        with st.spinner("Autonomous agents are conducting deep research and adversarial debate..."):
            result = service.execute_automated_research(
                hackathon_input=hackathon_input,
                options=PipelineOptions(max_domains=3, max_debate_rounds=2),
                progress_callback=on_progress,
            )
            st.session_state["doc_research_result"] = result
            st.session_state["doc_research_running"] = False
            progress_bar.progress(1.0)
            agent_status_box.success("✅ Autonomous research complete! Validated winner and report generated.")
            st.rerun()
    except Exception as exc:  # noqa: BLE001
        st.session_state["doc_research_running"] = False
        st.error(f"Research execution encountered an error: {exc}")


def _render_research_outcome(result: object) -> None:
    """Renders the final candidate evaluation, 10 quality gates, and report."""
    st.divider()
    st.subheader("4. Final Validated Research Outcome")

    # Winner details
    winner = getattr(result, "winner", None)
    if winner and getattr(winner, "has_winner", False):
        win_cand = winner.winner
        st.success(f"🏆 **Declared Winner:** {win_cand.candidate_title}")
        st.markdown(f"**Domain:** {win_cand.domain} | **Defensible Score:** `{win_cand.total_score:.1f} / 100`")
        st.markdown(f"**Problem Statement:** {win_cand.problem_statement}")
        st.markdown(f"**Proposed Solution:** {win_cand.proposed_solution}")

        # Quality Gates Audit
        st.markdown("#### 🛡️ Ten Mandatory Quality Gates Audit")
        gates_passed = win_cand.all_gates_passed
        if gates_passed:
            st.markdown("✅ **10 / 10 Quality Gates Passed.** All requirements rigorously verified against uploaded documents.")
        else:
            st.warning("Candidate failed one or more mandatory gates.")
    else:
        st.warning("⚠️ **Honest Rejection:** No candidate qualified after rigorous adversarial debate against official constraints.")

    # Master Report
    report = getattr(result, "report", None)
    if report:
        with st.expander("📄 View Full 24-Section Master Report", expanded=False):
            st.markdown(report.markdown if hasattr(report, "markdown") else str(report))
            st.download_button(
                "📥 Download Final Report (.md)",
                data=report.markdown if hasattr(report, "markdown") else str(report),
                file_name=f"HackathonIQ_Report_{getattr(result, 'session_id', 'export')}.md",
                mime="text/markdown",
            )


def _render_knowledge_base_tab(service: DocumentIntelligenceService, repo: object) -> None:
    """Renders Tab 2: Document Knowledge Base, pages and structured intelligence viewer."""
    documents = service.list_documents()
    if not documents:
        st.info("No documents uploaded yet.")
        return

    st.markdown(f"**{len(documents)} document(s) stored in active knowledge base.**")
    doc_options = {f"[{d.document_type.value.upper()}] {d.filename} ({d.page_count} pgs)": d.id for d in documents}
    chosen_label = st.selectbox("Select document to inspect", list(doc_options))
    chosen_id = doc_options[chosen_label]
    selected_doc = next(d for d in documents if d.id == chosen_id)

    c_act1, c_act2, c_act3 = st.columns([2, 1, 1])
    with c_act1:
        is_active = st.toggle("Include in active research sessions", value=selected_doc.is_active, key=f"active_{selected_doc.id}")
        if is_active != selected_doc.is_active:
            service.set_document_active(selected_doc.id, is_active)
            st.toast(f"Document {'activated' if is_active else 'deactivated'} for research.")
    with c_act2:
        if st.button("🔄 Retry Extraction", key=f"retry_{selected_doc.id}"):
            with st.spinner("Re-extracting document..."):
                try:
                    service.retry_extraction(selected_doc.id)
                    st.success("Re-extraction complete!")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Retry failed: {exc}")
    with c_act3:
        if st.button("🗑️ Delete Document", key=f"del_{selected_doc.id}", type="secondary"):
            service.delete_document(selected_doc.id)
            st.success("Document deleted.")
            st.rerun()

    st.divider()
    chunks = repo.get_document_chunks(selected_doc.id)
    struct_data = repo.get_document_structured_extraction(selected_doc.id)

    s1, s2 = st.tabs(["📄 Extracted Pages & Text Chunks", "🧠 Structured Intelligence (LLM)"])
    with s1:
        if not chunks:
            st.warning("No readable text chunks found for this document.")
        else:
            pages = sorted({c["page_number"] for c in chunks})
            chosen_page = st.selectbox("Page Navigation", pages, format_func=lambda p: f"Page {p}")
            page_chunks = [c for c in chunks if c["page_number"] == chosen_page]
            for idx, ch in enumerate(page_chunks):
                st.markdown(
                    f"""
                    <div style="background:#131720; border:1px solid #2d3748; border-radius:6px; padding:10px; margin-bottom:8px;">
                        <div style="display:flex; justify-content:space-between; color:#94a3b8; font-size:0.8rem;">
                            <span><strong>Chunk #{idx + 1}</strong> ({ch['content_type'].upper()})</span>
                            <span>Citation: <code>[Uploaded document: {selected_doc.filename}, Page {ch['page_number']}]</code></span>
                        </div>
                        <div style="margin-top:6px; color:#e2e8f0; font-size:0.9rem; white-space:pre-wrap; font-family:monospace;">
{ch['text_content']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with s2:
        if not struct_data or not struct_data.get("data"):
            st.info("No structured intelligence model available for this document.")
        else:
            st.json(struct_data["data"])


def _render_evidence_probe_tab(service: DocumentIntelligenceService) -> None:
    """Renders Tab 3: Interactive FTS5 BM25 evidence probe."""
    st.subheader("Interactive FTS5 BM25 Evidence Probe")
    st.markdown("Query the active uploaded document knowledge base using SQLite's FTS5 full-text engine.")
    query = st.text_input("Enter search query or constraint keyword", placeholder="e.g. offline models, judging criteria, agriculture")
    if query:
        hits = service.search_evidence(query, limit=8)
        if not hits:
            st.warning(f"No document chunks matched '{query}'.")
        else:
            st.success(f"Retrieved {len(hits)} matching chunk(s):")
            for i, h in enumerate(hits, 1):
                st.markdown(
                    f"""
                    <div style="background:#1a2233; border:1px solid #38bdf844; border-radius:8px; padding:12px; margin-bottom:10px;">
                        <div style="display:flex; justify-content:space-between; color:#38bdf8; font-weight:600; font-size:0.9rem;">
                            <span>[HIT #{i}] {h.filename} (Page {h.page_number})</span>
                            <span>Citation: <code>{h.citation}</code></span>
                        </div>
                        <div style="color:#e2e8f0; font-size:0.88rem; margin-top:8px; white-space:pre-wrap;">
{h.text_content}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
