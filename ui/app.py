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
from ui.components.common import APP_VERSION, get_llm, inject_css  # noqa: E402
from ui.pages import history, intelligence, new_research, results, settings  # noqa: E402

st.set_page_config(
    page_title="HackathonIQ",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

PAGES = {
    "New research": new_research.render,
    "Results": results.render,
    "History": history.render,
    "Intelligence": intelligence.render,
    "Settings": settings.render,
}

with st.sidebar:
    st.markdown(
        """
        <div style="padding: 4px 2px 14px 2px;">
            <div style="font-family:'Space Grotesk',sans-serif;font-size:1.55rem;font-weight:700;letter-spacing:-.03em;">
                Hackathon<span style="color:#f5b942;">IQ</span>
            </div>
            <div style="color:#9aa7b8;font-size:.82rem;margin-top:2px;">
                Evidence over ideas.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    choice = st.radio("Navigation", list(PAGES), key="nav_choice", label_visibility="collapsed")
    st.divider()

    config = get_settings()
    storage_report = StorageManager().get_storage_report()
    health = get_llm().health()
    st.markdown(
        f"""
        <div style="font-size:.8rem;color:#9aa7b8;line-height:1.7;">
            <div>Model · <span style="color:#e9edf2;">{health.get('active_model', config.ollama.model)}</span></div>
            <div>Ollama · <span style="color:{'#6ee7a8' if health.get('available') else '#f87171'};">
                {'online' if health.get('available') else 'offline'}</span></div>
            <div>Storage · <span style="color:#e9edf2;">{storage_report.used_gb:.2f} / {storage_report.budget_gb:.0f} GB</span></div>
            <div>Disk free · <span style="color:#e9edf2;">{storage_report.disk_free_gb:.0f} GB</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if storage_report.warnings:
        for warning in storage_report.warnings:
            st.warning(warning)
    st.divider()
    st.caption(
        "Five agents · dynamic domains · cross-domain competition · mandatory gates · "
        f"local inference · v{APP_VERSION}"
    )

try:
    PAGES[choice]()
except Exception as exc:  # noqa: BLE001 - never show a blank Streamlit page
    st.error(f"The page failed to render: {type(exc).__name__}: {exc}")
    with st.expander("Technical details"):
        import traceback

        st.code(traceback.format_exc())
