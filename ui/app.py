"""HackathonIQ Streamlit application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import get_settings  # noqa: E402
from src.storage.manager import StorageManager  # noqa: E402
import ui.components.common

try:
    from ui.components.common import APP_VERSION, PAGE_ALIASES, get_llm, inject_css  # noqa: E402
except ImportError:
    import importlib
    importlib.reload(ui.components.common)
    from ui.components.common import APP_VERSION, get_llm, inject_css  # noqa: E402
    PAGE_ALIASES = getattr(ui.components.common, "PAGE_ALIASES", {
        "Overview": "Overview",
        "New research": "New Research",
        "New Research": "New Research",
        "Research Workspace": "Research Workspace",
        "Workspace": "Research Workspace",
        "Results": "Results & Comparisons",
        "Results & Comparisons": "Results & Comparisons",
        "Documents": "Document Intelligence",
        "Document Intelligence": "Document Intelligence",
        "Playbook": "Hackathon Playbook",
        "Hackathon Playbook": "Hackathon Playbook",
        "History": "Research History",
        "Research History": "Research History",
        "Intelligence": "Document Intelligence",
        "Settings": "Settings",
    })
from ui.pages import (  # noqa: E402
    documents,
    history,
    new_research,
    overview,
    playbook,
    results,
    settings,
    workspace,
)

st.set_page_config(
    page_title="HackathonIQ",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

PAGES = {
    "Overview": overview.render,
    "New Research": new_research.render,
    "Research Workspace": workspace.render,
    "Results & Comparisons": results.render,
    "Document Intelligence": documents.render,
    "Hackathon Playbook": playbook.render,
    "Research History": history.render,
    "Settings": settings.render,
}

with st.sidebar:
    st.markdown(
        """
        <div style="padding: 6px 2px 16px 2px; border-bottom: 1px solid rgba(148, 163, 184, 0.12); margin-bottom: 12px;">
            <div style="font-size: 1.6rem; font-weight: 700; letter-spacing: -0.03em; color: #ffffff;">
                Hackathon<span style="color: #f59e0b;">IQ</span>
            </div>
            <div style="color: #94a3b8; font-size: 0.82rem; margin-top: 3px; font-weight: 500;">
                Evidence over ideas.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Active research badge in sidebar
    if st.session_state.get("research_in_progress"):
        st.markdown(
            """
            <div style="background: rgba(13, 148, 136, 0.15); border: 1px solid rgba(20, 184, 166, 0.4); border-radius: 8px; padding: 6px 12px; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                <span style="color: #14b8a6; font-size: 0.85rem;">●</span>
                <span style="color: #2dd4bf; font-size: 0.82rem; font-weight: 600;">Research in Progress</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Resolve safe programmatic navigation before radio instantiation
    if "target_nav" in st.session_state:
        target = st.session_state.pop("target_nav")
        canonical_target = PAGE_ALIASES.get(target, target)
        if canonical_target in PAGES:
            st.session_state["nav_choice"] = canonical_target

    choice = st.radio(
        "Navigation",
        list(PAGES),
        key="nav_choice",
        label_visibility="collapsed",
    )
    st.divider()

    config = get_settings()
    storage_report = StorageManager().get_storage_report()
    health = get_llm().health()

    status_color = "#34d399" if health.get("available") else "#f87171"
    status_text = "online" if health.get("available") else "offline"
    active_model = health.get("active_model", config.ollama.model)

    st.markdown(
        f"""
        <div style="font-size: 0.8rem; color: #94a3b8; line-height: 1.75; background: #0c121e; padding: 10px 14px; border-radius: 8px; border: 1px solid rgba(148, 163, 184, 0.1);">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span>Ollama Engine</span>
                <span style="color: {status_color}; font-weight: 600;">● {status_text}</span>
            </div>
            <div>Model · <span style="color: #f1f5f9; font-weight: 500;">{active_model.split(':')[0]}</span></div>
            <div>Storage · <span style="color: #f1f5f9;">{storage_report.used_gb:.2f} / {storage_report.budget_gb:.0f} GB</span></div>
            <div>Disk Free · <span style="color: #f1f5f9;">{storage_report.disk_free_gb:.0f} GB</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if storage_report.warnings:
        for warning in storage_report.warnings:
            st.warning(warning)
    st.divider()
    st.caption(
        "Five specialized agents · 10 mandatory quality gates · "
        f"autonomous idea selection · v{APP_VERSION}"
    )

try:
    PAGES[choice]()
except Exception as exc:  # noqa: BLE001 - never show a blank Streamlit page
    st.error(f"The page failed to render: {type(exc).__name__}: {exc}")
    with st.expander("Technical details"):
        import traceback

        st.code(traceback.format_exc())
