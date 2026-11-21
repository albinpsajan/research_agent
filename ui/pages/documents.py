"""Streamlit page: Document Intelligence, PDF & Image text extraction, and knowledge retrieval."""

from __future__ import annotations

import streamlit as st

from config.settings import get_settings
from src.knowledge.document_intelligence.extractor import OCREngine
from src.knowledge.document_intelligence.models import (
    DocumentType,
)
from src.knowledge.document_intelligence.service import DocumentIntelligenceService
from ui.components.common import get_llm, get_repository, hero


def render() -> None:
    hero(
        "Document Intelligence Studio",
        "Upload hackathon rulebooks, judging rubrics, scientific papers, or image evidence. "
        "Extract embedded text, tables, and scanned pages offline using local PyMuPDF/pypdf and Tesseract. "
        "Structured facts are parsed by Qwen and cited by all five AI agents.",
        eyebrow="Evidence & OCR",
    )

    settings = get_settings()
    repo = get_repository()
    llm = get_llm()
    service = DocumentIntelligenceService(repository=repo, llm=llm)

    ocr = OCREngine(tesseract_cmd=settings.document_intelligence.tesseract_cmd)
    ocr_available = ocr.is_available()

    if not ocr_available:
        st.info(
            "ℹ️ **Tesseract-OCR Note:** Embedded text in PDFs is fully extracted with 100% accuracy. "
            "For scanned physical pages or photo OCR, install Tesseract on Windows via: "
            "`winget install UB-Mannheim.TesseractOCR`."
        )

    tab1, tab2, tab3 = st.tabs([
        "📤 Upload & Ingest Documents",
        "📚 Knowledge Base & Extracted Content",
        "🔍 Evidence Search & Citation Probe",
    ])

    # ------------------------------------------------------------------
    # TAB 1: Upload & Ingest Documents
    # ------------------------------------------------------------------
    with tab1:
        st.subheader("Upload Research & Event Documents")
        st.markdown(
            "Supported formats: **PDF** (digital and scanned), **JPG/JPEG**, **PNG**, **WEBP**. "
            f"Maximum file size: **{settings.document_intelligence.max_file_size_mb} MB**, "
            f"up to **{settings.document_intelligence.max_pages_per_doc} pages** per document."
        )

        col_left, col_right = st.columns([2, 1])
        with col_left:
            uploaded_files = st.file_uploader(
                "Select one or more documents to upload",
                type=["pdf", "jpg", "jpeg", "png", "webp"],
                accept_multiple_files=True,
                key="doc_intel_uploader",
            )
        with col_right:
            doc_type_choice = st.selectbox(
                "Document Classification",
                [
                    "Official Hackathon Rulebook / Guide",
                    "Research Paper / Whitepaper",
                    "Technical Architecture / Spec",
                    "Dataset Documentation / Dictionary",
                    "General Community / Ground Evidence",
                ],
                index=0,
                help="Classifying as an Official Rulebook gives it highest priority for criteria, eligibility and restriction checks.",
            )

            type_mapping = {
                "Official Hackathon Rulebook / Guide": DocumentType.OFFICIAL_RULES,
                "Research Paper / Whitepaper": DocumentType.RESEARCH_PAPER,
                "Technical Architecture / Spec": DocumentType.TECHNICAL_SPEC,
                "Dataset Documentation / Dictionary": DocumentType.DATASET_DOCUMENTATION,
                "General Community / Ground Evidence": DocumentType.GENERAL_EVIDENCE,
            }
            doc_type = type_mapping[doc_type_choice]
            run_structuring = st.checkbox(
                "Run local LLM structured extraction (Qwen)",
                value=True,
                help="Automatically extracts structured rules, criteria, and facts into queryable Pydantic models.",
            )

        if uploaded_files and st.button("🚀 Ingest & Extract Selected Documents", type="primary"):
            progress_bar = st.progress(0)
            status_box = st.empty()
            success_count = 0

            for i, file in enumerate(uploaded_files):
                status_box.markdown(f"**Extracting ({i + 1}/{len(uploaded_files)}):** `{file.name}`...")
                file_bytes = file.read()
                try:
                    doc = service.upload_document(
                        filename=file.name,
                        file_bytes=file_bytes,
                        document_type=doc_type,
                        extract_structured=run_structuring,
                    )
                    success_count += 1
                    st.success(
                        f"✅ **{doc.filename}** ingested: {doc.page_count} page(s) extracted "
                        f"via `{doc.extraction_method.value}` ({len(file_bytes) / 1024:.1f} KB)."
                    )
                    if doc.warnings:
                        with st.expander(f"⚠️ Warnings for {doc.filename}"):
                            for w in doc.warnings:
                                st.warning(w)
                except Exception as exc:  # noqa: BLE001
                    st.error(f"❌ Failed to extract `{file.name}`: {exc}")

                progress_bar.progress((i + 1) / len(uploaded_files))

            status_box.markdown(f"🎉 **Ingestion complete!** {success_count}/{len(uploaded_files)} document(s) added to knowledge base.")
            st.rerun()

    # ------------------------------------------------------------------
    # TAB 2: Knowledge Base & Extracted Content
    # ------------------------------------------------------------------
    with tab2:
        documents = service.list_documents()
        if not documents:
            st.info("No documents uploaded yet. Use the 'Upload & Ingest' tab to add documents.")
        else:
            st.markdown(f"**{len(documents)} document(s) stored in active knowledge base.**")
            doc_options = {f"[{d.document_type.value.upper()}] {d.filename} ({d.page_count} pgs)": d.id for d in documents}
            chosen_label = st.selectbox("Select document to inspect", list(doc_options))
            chosen_id = doc_options[chosen_label]

            selected_doc = next(d for d in documents if d.id == chosen_id)

            # Control buttons
            c_actions1, c_actions2, c_actions3 = st.columns([2, 1, 1])
            with c_actions1:
                is_active = st.toggle("Include in active research sessions", value=selected_doc.is_active, key=f"active_{selected_doc.id}")
                if is_active != selected_doc.is_active:
                    service.set_document_active(selected_doc.id, is_active)
                    st.toast(f"Document {'activated' if is_active else 'deactivated'} for research.")
            with c_actions2:
                if st.button("🔄 Retry Extraction", key=f"retry_{selected_doc.id}"):
                    with st.spinner("Re-extracting document..."):
                        try:
                            service.retry_extraction(selected_doc.id)
                            st.success("Re-extraction complete!")
                            st.rerun()
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"Retry failed: {exc}")
            with c_actions3:
                if st.button("🗑️ Delete Document", key=f"del_{selected_doc.id}", type="secondary"):
                    service.delete_document(selected_doc.id)
                    st.success("Document deleted.")
                    st.rerun()

            st.divider()

            # Metadata header
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Format", selected_doc.file_type.upper())
            m2.metric("Pages", selected_doc.page_count)
            m3.metric("Size", f"{selected_doc.file_size / 1024:.1f} KB")
            m4.metric("Method", selected_doc.extraction_method.value)

            # View Chunks / Pages
            chunks = repo.get_document_chunks(selected_doc.id)
            struct_data = repo.get_document_structured_extraction(selected_doc.id)

            sub_tab1, sub_tab2 = st.tabs(["📄 Extracted Pages & Text", "🧠 Structured Intelligence (LLM)"])

            with sub_tab1:
                if not chunks:
                    st.warning("No readable text chunks found for this document.")
                else:
                    pages = sorted({c["page_number"] for c in chunks})
                    chosen_page = st.selectbox("Page Navigation", pages, format_func=lambda p: f"Page {p}")

                    page_chunks = [c for c in chunks if c["page_number"] == chosen_page]
                    for idx, ch in enumerate(page_chunks):
                        st.markdown(
                            f"""
                            <div style="background: #131720; border: 1px solid #2d3748; border-radius: 6px; padding: 10px; margin-bottom: 8px;">
                                <div style="display:flex; justify-content:space-between; color: #94a3b8; font-size: 0.8rem;">
                                    <span><strong>Chunk #{idx + 1}</strong> ({ch['content_type'].upper()})</span>
                                    <span>Citation: <code>[Uploaded document: {selected_doc.filename}, Page {ch['page_number']}]</code></span>
                                </div>
                                <div style="margin-top: 6px; color: #e2e8f0; font-size: 0.9rem; white-space: pre-wrap; font-family: monospace;">
{ch['text_content']}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

            with sub_tab2:
                if not struct_data or not struct_data.get("data"):
                    st.info("No structured intelligence model available for this document.")
                else:
                    data = struct_data["data"]
                    if struct_data.get("extraction_type") == "hackathon_profile":
                        st.subheader(f"🏆 {data.get('hackathon_name') or selected_doc.filename}")
                        if data.get("organizer"):
                            st.markdown(f"**Organizer:** {data.get('organizer')}")
                        if data.get("theme"):
                            st.markdown(f"**Theme:** {data.get('theme')}")
                        if data.get("event_duration"):
                            st.markdown(f"**Duration:** {data.get('event_duration')}")

                        c_left, c_right = st.columns(2)
                        with c_left:
                            st.markdown("#### ⚖️ Official Judging Criteria")
                            for cr in data.get("judging_criteria", []):
                                st.markdown(f"- {cr}")

                            st.markdown("#### 🎯 Tracks & Themes")
                            for tr in data.get("tracks", []):
                                st.markdown(f"- {tr}")

                            st.markdown("#### 🛑 Technical Restrictions")
                            for res in data.get("technical_restrictions", []):
                                st.markdown(f"- {res}")

                        with c_right:
                            st.markdown("#### 📋 Eligibility & Rules")
                            for el in data.get("eligibility_requirements", []):
                                st.markdown(f"- {el}")

                            st.markdown("#### 📦 Required Technologies")
                            for tech in data.get("required_technologies", []):
                                st.markdown(f"- {tech}")

                            st.markdown("#### 📅 Important Deadlines")
                            for dl in data.get("important_deadlines", []):
                                st.markdown(f"- {dl}")

                        st.divider()
                        st.markdown("#### 🔎 Provenance Separation")
                        f_col, i_col, u_col = st.columns(3)
                        with f_col:
                            st.success("**Directly Extracted Facts**")
                            for f in data.get("extracted_facts", []):
                                st.markdown(f"- {f}")
                        with i_col:
                            st.info("**Reasonable Inferences**")
                            for inf in data.get("inferences", []):
                                st.markdown(f"- {inf}")
                        with u_col:
                            st.warning("**Unverified Details**")
                            for unv in data.get("unverified_items", []):
                                st.markdown(f"- {unv}")
                    else:
                        st.subheader(f"📑 {data.get('document_title') or selected_doc.filename}")
                        if data.get("authors_or_institution"):
                            st.markdown(f"**Author / Institution:** {data.get('authors_or_institution')}")
                        if data.get("target_geography"):
                            st.markdown(f"**Target Geography:** {data.get('target_geography')}")

                        r1, r2 = st.columns(2)
                        with r1:
                            st.markdown("#### 💡 Key Findings & Ground Facts")
                            for kf in data.get("key_findings", []):
                                st.markdown(f"- {kf}")

                            st.markdown("#### 🚨 Problems Identified")
                            for p in data.get("problems_identified", []):
                                st.markdown(f"- {p}")

                        with r2:
                            st.markdown("#### 📊 Datasets & Methods")
                            for ds in data.get("datasets_and_methodologies", []):
                                st.markdown(f"- {ds}")

                            st.markdown("#### ⚙️ Technical Feasibility Insights")
                            for tf in data.get("technical_feasibility_insights", []):
                                st.markdown(f"- {tf}")

    # ------------------------------------------------------------------
    # TAB 3: Evidence Search & Citation Probe
    # ------------------------------------------------------------------
    with tab3:
        st.subheader("Interactive FTS5 BM25 Evidence Probe")
        st.markdown(
            "Test how the 5 AI agents search and retrieve relevant document chunks using "
            "SQLite's built-in FTS5 full-text engine."
        )

        search_query = st.text_input(
            "Enter research query or restriction keyword",
            placeholder="e.g. offline models, judging criteria, agricultural vulnerability, dataset schema",
        )

        if search_query:
            hits = service.search_evidence(search_query, limit=8)
            if not hits:
                st.warning(f"No document chunks matched '{search_query}'.")
            else:
                st.success(f"Retrieved {len(hits)} relevant chunk(s):")
                for i, h in enumerate(hits, 1):
                    st.markdown(
                        f"""
                        <div style="background: #1a2233; border: 1px solid #38bdf844; border-radius: 8px; padding: 12px; margin-bottom: 10px;">
                            <div style="display:flex; justify-content:space-between; color: #38bdf8; font-weight: 600; font-size: 0.9rem;">
                                <span>[HIT #{i}] {h.filename} (Page {h.page_number})</span>
                                <span>Citation: <code>{h.citation}</code></span>
                            </div>
                            <div style="color: #94a3b8; font-size: 0.8rem; margin-top: 2px;">
                                Type: {h.document_type.value} | Method: {h.extraction_method} | Confidence: {h.confidence:.2f}
                            </div>
                            <div style="color: #e2e8f0; font-size: 0.88rem; margin-top: 8px; line-height: 1.5; white-space: pre-wrap;">
{h.text_content}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
