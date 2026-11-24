"""HackathonIQ — Simplified ChatGPT-style SaaS Application Entry Point.

Only TWO user-facing navigation destinations:
1. New Research
2. History
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import get_settings  # noqa: E402
from src.storage.manager import StorageManager  # noqa: E402
import ui.components.common  # noqa: E402

try:
    from ui.components.common import APP_VERSION, PAGE_ALIASES, get_llm, get_repository, inject_css  # noqa: E402
except ImportError:
    import importlib
    importlib.reload(ui.components.common)
    from ui.components.common import APP_VERSION, PAGE_ALIASES, get_llm, get_repository, inject_css  # noqa: E402

from ui.pages import history, new_research  # noqa: E402

st.set_page_config(
    page_title="HackathonIQ — Evidence over ideas",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

# The application strictly has ONLY TWO primary user-facing pages
PAGES = {
    "New Research": new_research.render,
    "History": history.render,
}

with st.sidebar:
    # 1. HackathonIQ Branding
    st.markdown(
        """
        <div style="padding: 10px 4px 18px 4px; border-bottom: 1px solid rgba(148, 163, 184, 0.12); margin-bottom: 14px;">
            <div style="font-size: 1.55rem; font-weight: 700; letter-spacing: -0.03em; color: #ffffff;">
                Hackathon<span style="color: #f59e0b;">IQ</span>
            </div>
            <div style="color: #14b8a6; font-size: 0.8rem; margin-top: 3px; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;">
                Evidence over ideas.
            </div>
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

    # 2. Main Two Navigation Destinations
    choice = st.radio(
        "Navigation",
        list(PAGES),
        key="nav_choice",
        label_visibility="collapsed",
    )

    # 3. ChatGPT-style Recent Sessions in Sidebar for Quick 1-Click Access
    repo = get_repository()
    recent_sessions = repo.list_sessions(limit=8)

    if recent_sessions:
        st.markdown(
            """
            <div style="font-size: 0.72rem; color: #64748b; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin: 18px 0 8px 4px;">
                Recent Research
            </div>
            """,
            unsafe_allow_html=True,
        )
        for s in recent_sessions[:6]:
            s_id = s["id"]
            name = s.get("hackathon_name") or s.get("hackathon_theme") or "Untitled Session"
            short_name = (name[:26] + "…") if len(name) > 26 else name
            is_active = (s_id == st.session_state.get("current_session_id"))

            col_btn, _ = st.columns([1, 0.01])
            with col_btn:
                btn_type = "primary" if is_active else "secondary"
                if st.button(
                    f"◈ {short_name}",
                    key=f"sb_sess_{s_id}",
                    type=btn_type,
                    use_container_width=True,
                ):
                    # Load session into results and switch to New Research view
                    st.session_state["target_session_to_load"] = s_id
                    st.session_state["nav_choice"] = "New Research"
                    st.rerun()

    st.divider()

    # 4. Minimal, Unobtrusive Footer: Model & Engine Status
    config = get_settings()
    health = get_llm().health()
    status_color = "#10b981" if health.get("available") else "#ef4444"
    status_text = "online" if health.get("available") else "offline"
    active_model = (health.get("active_model", config.ollama.model) or "qwen2.5:3b").split(":")[0]

    st.markdown(
        f"""
        <div style="font-size: 0.78rem; color: #94a3b8; display: flex; justify-content: space-between; align-items: center; padding: 4px 6px;">
            <span><span style="color: {status_color};">●</span> Ollama {status_text}</span>
            <span style="color: #cbd5e1; font-family: monospace;">{active_model}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"HackathonIQ v{APP_VERSION} · 100% Local Inference")

# Render active page
try:
    PAGES[choice]()
except Exception as exc:  # noqa: BLE001
    st.error(f"The page failed to render: {type(exc).__name__}: {exc}")
    with st.expander("Technical details"):
        import traceback
        st.code(traceback.format_exc())
