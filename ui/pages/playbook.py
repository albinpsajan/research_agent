"""HackathonIQ Streamlit page: Hackathon Playbook & Official Source Registry."""

from __future__ import annotations

import streamlit as st

from src.knowledge.hackathon_playbook.database import PlaybookDatabase
from src.knowledge.hackathon_playbook.schema import PlaybookCategory
from src.research.sources.kerala_india_registry import KeralaIndiaSourceRegistry, SourceCoverageStatus


def render() -> None:
    st.markdown(
        """
        <div style="padding-bottom: 12px;">
            <div style="font-size: 1.8rem; font-weight: 700; color: #e9edf2;">
                Hackathon <span style="color: #f5b942;">Playbook</span> & Source Registry
            </div>
            <div style="color: #9aa7b8; font-size: 0.95rem;">
                Curated competition heuristics, winning patterns, judge insights, and authoritative Kerala, India & Global data sources.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    db = PlaybookDatabase()
    registry = KeralaIndiaSourceRegistry()

    all_entries = db.list_all(limit=100)
    summary = registry.get_coverage_summary()

    # Top high-level metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Playbook Lessons", len(all_entries))
    with col2:
        st.metric("Official Sources", summary["total_official_sources"])
    with col3:
        st.metric("Kerala & India Sources", summary["by_geography"].get("kerala", 0) + summary["by_geography"].get("india", 0))
    with col4:
        st.metric("Global Portals", summary["by_geography"].get("global", 0))

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs([
        "◈ Playbook Lessons & Heuristics",
        "🌐 Official Source Registry",
        "⚖️ Judge Insights & Failure Patterns",
    ])

    with tab1:
        st.subheader("Curated Competition Lessons (FTS5 Indexed)")
        search_col, cat_col, agent_col = st.columns([2, 1, 1])
        with search_col:
            search_query = st.text_input("Search lessons (FTS5 full-text)", placeholder="e.g. offline, sensor, wrapper, demo, kerala")
        with cat_col:
            cat_options = ["All Categories"] + [c.value for c in PlaybookCategory]
            selected_cat = st.selectbox("Category Filter", cat_options)
        with agent_col:
            agent_options = [
                "All Agents",
                "agent_1_intelligence",
                "agent_2_domain",
                "agent_3_research",
                "agent_4_solution",
                "agent_5_critic",
            ]
            selected_agent = st.selectbox("Target Agent", agent_options)

        category_filter = None if selected_cat == "All Categories" else selected_cat
        agent_filter = None if selected_agent == "All Agents" else selected_agent

        if search_query.strip():
            displayed_entries = db.search(
                query=search_query.strip(),
                category=category_filter,
                target_agent=agent_filter,
                limit=50,
            )
        else:
            displayed_entries = [
                e for e in all_entries
                if (not category_filter or e.category.value == category_filter)
                and (not agent_filter or e.target_agent in {agent_filter, "all"})
            ]

        st.caption(f"Showing {len(displayed_entries)} playbook lesson(s)")

        for entry in displayed_entries:
            with st.expander(f"[{entry.id}] {entry.title} ({entry.category.value.replace('_', ' ').title()})"):
                st.markdown(f"**Target Agent:** `{entry.target_agent}` | **Source Origin:** *{entry.source_origin}* | **Confidence:** `{entry.confidence:.2f}`")
                st.markdown(f"**Lesson:**\n{entry.lesson}")
                st.info(f"**Actionable Guidance for Agents:**\n{entry.actionable_guidance}")
                st.markdown(f"**Kerala & India Localization:**\n{entry.kerala_india_applicability}")
                if entry.tags:
                    tags_badges = " ".join([f"`{t}`" for t in entry.tags])
                    st.markdown(f"**Tags:** {tags_badges}")

    with tab2:
        st.subheader("Authoritative Kerala, India & Global Source Registry")
        geo_col, topic_col = st.columns([1, 2])
        with geo_col:
            geo_choice = st.selectbox("Geographical Scope", ["All", "Kerala", "India", "Global"])
        with topic_col:
            topic_search = st.text_input("Filter by Topic or Name", placeholder="e.g. agriculture, satellite, health, disaster")

        filtered_sources = registry.catalog
        if geo_choice != "All":
            filtered_sources = [s for s in filtered_sources if s.geography.lower() == geo_choice.lower()]
        if topic_search.strip():
            term = topic_search.strip().lower()
            filtered_sources = [
                s for s in filtered_sources
                if term in s.name.lower() or term in s.description.lower() or any(term in t.lower() for t in s.topics)
            ]

        st.caption(f"Showing {len(filtered_sources)} official source portal(s)")

        for src in filtered_sources:
            status_color = "#6ee7a8" if src.status == SourceCoverageStatus.INTEGRATED else "#f5b942"
            with st.container():
                st.markdown(
                    f"""
                    <div style="border: 1px solid #2d3748; border-radius: 8px; padding: 12px; margin-bottom: 12px; background: #131720;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div style="font-weight: 600; font-size: 1.05rem; color: #e9edf2;">
                                [{src.id}] {src.name}
                            </div>
                            <div>
                                <span style="background: {status_color}22; color: {status_color}; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">
                                    {src.status.value.upper()}
                                </span>
                                <span style="background: #2a3447; color: #cbd5e1; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; margin-left: 6px;">
                                    {src.geography.upper()}
                                </span>
                            </div>
                        </div>
                        <div style="color: #94a3b8; font-size: 0.85rem; margin-top: 4px;">
                            <strong>Authority:</strong> {src.authority} | <strong>Access:</strong> {src.access_type} | <strong>Formats:</strong> {', '.join(src.data_formats)}
                        </div>
                        <div style="color: #cbd5e1; font-size: 0.88rem; margin-top: 6px;">
                            {src.description}
                        </div>
                        <div style="margin-top: 6px; font-size: 0.8rem;">
                            <a href="{src.base_url}" target="_blank" style="color: #38bdf8; text-decoration: none;">🔗 Visit Official Portal: {src.base_url}</a>
                        </div>
                        <div style="margin-top: 6px;">
                            {' '.join([f'<span style=\"background:#1e293b;color:#94a3b8;padding:1px 6px;border-radius:3px;font-size:0.75rem;margin-right:4px;\">#{t}</span>' for t in src.topics])}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with tab3:
        st.subheader("Hackathon Judge Insights & Common Failure Patterns")
        domain_tab = st.selectbox(
            "Select Evaluation Domain Focus",
            [
                "Climate-Resilient Agriculture & Environment",
                "Healthcare & Epidemiology Surveillance",
                "Education, Vernacular Learning & Public Governance",
                "Disaster Risk & Geospatial Early Warning",
            ],
        )

        col_left, col_right = st.columns(2)
        with col_left:
            st.error("⚠️ What Causes Instant Rejection / Low Scoring")
            if "Agriculture" in domain_tab:
                st.markdown(
                    """
                    - **Thin API Wrapper**: Simply sending farmer queries to a generic cloud LLM without localized agronomic calibration.
                    - **Ignoring Farm Geometry**: Assuming 50-hectare monoculture fields instead of Kerala's <0.5 ha multi-tier homestead plots.
                    - **Cloud Sensor Assumption**: Presuming reliable 5G/4G connectivity on steep hillside plantations or low polders.
                    - **Unrealistic Hardware Costs**: Proposing expensive IoT soil probe arrays for smallholders whose gross crop margin is <$300/yr.
                    """
                )
            elif "Healthcare" in domain_tab:
                st.markdown(
                    """
                    - **Unvalidated Clinical AI**: Claiming diagnostic accuracy without verified clinical datasets or ICMR doctor validation.
                    - **Ignoring Local Vector Dynamics**: Modeling dengue without humidity/rubber plantation rainwater pooling data.
                    - **Monolingual Telemedicine**: Building English-only chatbots that cannot serve elderly or rural vernacular patients.
                    """
                )
            elif "Education" in domain_tab:
                st.markdown(
                    """
                    - **Generic Flashcard/Quiz App**: Building a standard chatbot that answers math questions without vernacular pedagogy.
                    - **Ignoring State Curricula**: Overlooking SCERT/Samagra Kerala state syllabus alignment.
                    - **Bandwidth Heavy Video Streams**: Assuming students have unlimited fiber broadband.
                    """
                )
            else:
                st.markdown(
                    """
                    - **Delayed Satellite Revisit Latency**: Relying on 5-day optical revisit imagery for flash flood or sudden landslide early warnings.
                    - **Optical Cloud Blindness**: Forgetting that monsoon cloud cover blinds optical sensors for weeks in Wayanad and Idukki.
                    """
                )

        with col_right:
            st.success("✅ Winning Patterns & Strategic Differentiation")
            if "Agriculture" in domain_tab:
                st.markdown(
                    """
                    - **Hyper-Local Open Data Integration**: Grounded in KAU Agromet Bulletins, DES ODR yields, and IMD 0.25° gridded rainfall.
                    - **Offline-First Resilience**: Local SQLite/PWA cache enabling 100% offline advisory with opportunistic sync.
                    - **Hero Flow Live Demo**: Demonstrating a 3-minute concrete walkthrough using realistic Wayanad/Kuttanad farm profiles.
                    - **Zero Cost Deployment**: Zero paid recurring API subscriptions, operating cleanly on open-source libraries.
                    """
                )
            elif "Healthcare" in domain_tab:
                st.markdown(
                    """
                    - **Official DHS & ICMR Protocol Alignment**: Direct grounding in Kerala public health guidelines.
                    - **Malayalam Vernacular Voice Support**: Conversational voice prompts for low-literacy users.
                    - **Triage & Human-in-the-Loop**: Clear escalation to local Primary Health Centre (PHC) medical officers.
                    """
                )
            elif "Education" in domain_tab:
                st.markdown(
                    """
                    - **Vernacular Malayalam Pedagogical Scaffolding**: Dialect-aware tutoring grounded in SCERT standards.
                    - **Audio & Offline Worksheets**: Lightweight delivery via voice notes or cached offline interactive modules.
                    """
                )
            else:
                st.markdown(
                    """
                    - **All-Weather Synthetic Aperture Radar (SAR)**: Using Sentinel-1 C-band SAR to penetrate monsoon cloud cover.
                    - **Pre-computed Susceptibility Maps**: Integrating KSDMA hazard micro-zonation with real-time IMD rainfall alerts.
                    """
                )
