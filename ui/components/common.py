"""Shared Streamlit helpers, visual design system, and component primitives."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.logging_config import setup_logging  # noqa: E402
from src.database.migrations import initialize_database  # noqa: E402
from src.database.repository import Repository  # noqa: E402
from src.llm.client import OllamaClient  # noqa: E402

APP_VERSION = "2.5.0"

# Canonical page name mappings: only TWO primary pages (New Research & History)
PAGE_ALIASES: dict[str, str] = {
    "New research": "New Research",
    "New Research": "New Research",
    "History": "History",
    "Research History": "History",
    "Results": "New Research",
    "Results & Comparisons": "New Research",
    "Overview": "New Research",
    "Workspace": "New Research",
    "Research Workspace": "New Research",
    "Documents": "New Research",
    "Document Intelligence": "New Research",
    "Playbook": "New Research",
    "Hackathon Playbook": "New Research",
    "Settings": "New Research",
}


def inject_css() -> None:
    """Inject HackathonIQ ChatGPT-inspired dark theme design system CSS."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

        :root {
            /* Canvas & Surfaces */
            --canvas: #0b0f17;
            --panel: #111827;
            --panel-elevated: #1e293b;
            --panel-hover: #243248;
            --line: rgba(148, 163, 184, 0.12);
            --line-strong: rgba(148, 163, 184, 0.22);

            /* Typography */
            --text-primary: #f8fafc;
            --text-muted: #94a3b8;
            --text-subdued: #64748b;

            /* Brand & Accent Tokens */
            --teal: #0d9488;
            --teal-bright: #14b8a6;
            --teal-subtle: rgba(13, 148, 136, 0.12);
            --gold: #f59e0b;
            --gold-bright: #fbbf24;
            --gold-subtle: rgba(245, 158, 11, 0.12);

            /* Status Signals */
            --ok: #10b981;
            --ok-subtle: rgba(16, 185, 129, 0.12);
            --danger: #ef4444;
            --danger-subtle: rgba(239, 68, 68, 0.12);
            --warn: #f59e0b;
            --warn-subtle: rgba(245, 158, 11, 0.12);

            /* Radii & Shadows */
            --radius-sm: 6px;
            --radius-md: 10px;
            --radius-lg: 14px;
        }

        /* Base Streamlit App Overrides */
        .stApp {
            background-color: var(--canvas);
            color: var(--text-primary);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        h1, h2, h3, h4, h5, h6 {
            color: var(--text-primary);
            font-weight: 600;
            letter-spacing: -0.02em;
        }

        /* ChatGPT-style Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: #0d131f;
            border-right: 1px solid var(--line);
        }

        /* Remove Streamlit's automatically generated multi-page sidebar navigation */
        [data-testid="stSidebarNav"],
        div[data-testid="stSidebarNav"],
        nav[data-testid="stSidebarNav"],
        ul[data-testid="stSidebarNavItems"],
        header[data-testid="stSidebarNavHeader"],
        div[data-testid="stSidebarNavSeparator"] {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            pointer-events: none !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
            gap: 0.5rem;
        }

        /* Welcome Hero */
        .chatgpt-hero {
            text-align: center;
            max-width: 720px;
            margin: 28px auto 24px auto;
        }

        .chatgpt-hero h1 {
            font-size: 2.3rem;
            font-weight: 700;
            letter-spacing: -0.03em;
            margin: 0 0 6px 0;
            color: #ffffff;
        }

        .chatgpt-hero .tagline {
            color: var(--teal-bright);
            font-size: 0.98rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 12px;
        }

        .chatgpt-hero p {
            color: var(--text-muted);
            font-size: 1.02rem;
            line-height: 1.6;
            margin: 0;
        }

        /* Clean Card Surfaces */
        .hiq-card {
            border: 1px solid var(--line);
            border-radius: var(--radius-md);
            padding: 18px 22px;
            background-color: var(--panel);
            margin-bottom: 16px;
        }

        .hiq-winner {
            border: 1px solid rgba(245, 158, 11, 0.4);
            background: linear-gradient(145deg, rgba(245, 158, 11, 0.08) 0%, rgba(13, 148, 136, 0.04) 100%), #111827;
            border-radius: var(--radius-lg);
            padding: 24px 28px;
            margin-bottom: 22px;
        }

        .hiq-winner .label {
            color: var(--gold-bright);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.72rem;
            font-weight: 700;
            margin-bottom: 8px;
            display: inline-block;
        }

        .hiq-winner h2 {
            margin: 0 0 10px 0;
            font-size: 1.7rem;
            color: #ffffff;
        }

        /* Status Badges */
        .hiq-pill {
            display: inline-flex;
            align-items: center;
            padding: 3px 10px;
            border-radius: 9999px;
            border: 1px solid var(--line);
            color: var(--text-muted);
            font-size: 0.78rem;
            font-weight: 500;
            margin-right: 6px;
            margin-bottom: 6px;
            background: rgba(17, 24, 39, 0.6);
        }

        .hiq-pill.ok {
            color: #34d399;
            background: var(--ok-subtle);
            border-color: rgba(52, 211, 153, 0.3);
        }

        .hiq-pill.bad {
            color: #f87171;
            background: var(--danger-subtle);
            border-color: rgba(248, 113, 113, 0.3);
        }

        .hiq-pill.warn {
            color: var(--gold-bright);
            background: var(--warn-subtle);
            border-color: rgba(245, 158, 11, 0.3);
        }

        .hiq-pill.teal {
            color: var(--teal-bright);
            background: var(--teal-subtle);
            border-color: rgba(20, 184, 166, 0.3);
        }

        .hiq-pill.gold {
            color: var(--gold-bright);
            background: var(--gold-subtle);
            border-color: rgba(245, 158, 11, 0.35);
        }

        /* Buttons — Teal Primary Accent */
        .stButton > button[kind="primary"], .stButton > button[type="primary"] {
            border-radius: var(--radius-sm);
            border: 1px solid var(--teal-bright);
            background: linear-gradient(180deg, #0d9488 0%, #0f766e 100%);
            color: #ffffff;
            font-weight: 600;
            letter-spacing: -0.01em;
            padding: 8px 18px;
            transition: all 0.15s ease-in-out;
        }

        .stButton > button[kind="primary"]:hover, .stButton > button[type="primary"]:hover {
            background: linear-gradient(180deg, #14b8a6 0%, #0d9488 100%);
            border-color: #2dd4bf;
            color: #ffffff;
        }

        /* Secondary Buttons */
        .stButton > button:not([kind="primary"]):not([type="primary"]),
        .stDownloadButton > button {
            border-radius: var(--radius-sm);
            border: 1px solid var(--line-strong);
            background: var(--panel);
            color: var(--text-primary);
            font-weight: 500;
            transition: all 0.15s ease-in-out;
        }

        .stButton > button:not([kind="primary"]):not([type="primary"]):hover,
        .stDownloadButton > button:hover {
            border-color: var(--teal);
            color: #ffffff;
            background: var(--panel-elevated);
        }

        /* Progress Bar & Stepper */
        div[data-testid="stProgress"] > div > div > div > div {
            background: linear-gradient(90deg, #0d9488 0%, #14b8a6 100%);
        }

        /* Metric Boxes */
        div[data-testid="stMetric"] {
            background-color: var(--panel);
            border: 1px solid var(--line);
            border-radius: var(--radius-md);
            padding: 12px 16px;
        }

        div[data-testid="stMetricLabel"] {
            color: var(--text-muted);
            font-size: 0.8rem;
            text-transform: uppercase;
        }

        div[data-testid="stMetricValue"] {
            color: #ffffff;
            font-size: 1.45rem;
            font-weight: 700;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
            border-bottom: 1px solid var(--line);
            margin-bottom: 16px;
        }

        .stTabs [data-baseweb="tab"] {
            background: transparent;
            border: none;
            border-radius: var(--radius-sm);
            padding: 8px 14px;
            color: var(--text-muted);
            font-weight: 500;
        }

        .stTabs [aria-selected="true"] {
            background-color: var(--panel-elevated) !important;
            color: var(--teal-bright) !important;
            border: 1px solid rgba(20, 184, 166, 0.3) !important;
            font-weight: 600;
        }

        /* Expanders */
        div[data-testid="stExpander"] {
            border: 1px solid var(--line);
            border-radius: var(--radius-md);
            background-color: rgba(17, 24, 39, 0.7);
            margin-bottom: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero(title: str, subtitle: str, eyebrow: str = "HackathonIQ", badge_text: str | None = None) -> None:
    """Render a consistent page hero header."""
    badge_html = f'<span class="hiq-pill teal" style="margin-left:8px;">{badge_text}</span>' if badge_text else ""
    st.markdown(
        f"""
        <div style="border: 1px solid rgba(148, 163, 184, 0.12); border-radius: 12px; padding: 20px 24px; background: #111827; margin-bottom: 18px;">
            <div style="color: #14b8a6; font-size: 0.75rem; text-transform: uppercase; font-weight: 700; letter-spacing: 0.1em; margin-bottom: 4px;">
                {eyebrow}{badge_html}
            </div>
            <h1 style="font-size: 1.75rem; font-weight: 700; color: #ffffff; margin: 0 0 6px 0;">{title}</h1>
            <p style="color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin: 0;">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str, eyebrow: str = "HackathonIQ", badge_text: str | None = None) -> None:
    hero(title, subtitle, eyebrow=eyebrow, badge_text=badge_text)


def empty_state(title: str, description: str, icon: str = "◈", cta_label: str | None = None, cta_page: str | None = None) -> None:
    st.markdown(
        f"""
        <div style="border: 1px dashed rgba(148, 163, 184, 0.2); border-radius: 12px; padding: 36px 24px; text-align: center; background: rgba(17, 24, 39, 0.4); margin: 20px 0;">
            <div style="font-size: 2rem; color: #94a3b8; margin-bottom: 6px;">{icon}</div>
            <h3 style="color: #ffffff; margin: 4px 0 6px 0;">{title}</h3>
            <p style="color: #94a3b8; font-size: 0.92rem; max-width: 500px; margin: 0 auto 14px auto;">{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if cta_label and cta_page:
        col_p1, col_b, col_p2 = st.columns([2, 1, 2])
        with col_b:
            if st.button(cta_label, type="primary", use_container_width=True, key=f"empty_cta_{cta_page}"):
                navigate_to(cta_page)


@st.cache_resource
def get_repository() -> Repository:
    setup_logging()
    repository = Repository()
    initialize_database(repository.db)
    return repository


@st.cache_resource
def get_llm() -> OllamaClient:
    return OllamaClient()


def reset_caches() -> None:
    get_llm.clear()
    get_repository.clear()


def ollama_banner() -> dict:
    health = get_llm().health()
    if not health.get("available"):
        st.error(
            "Ollama is offline. Start the Ollama server on your system, then refresh this page."
        )
    return health


def badge(text: str, kind: str = "") -> str:
    return f'<span class="hiq-pill {kind}">{text}</span>'


def status_pill(text: str, kind: str = "") -> str:
    return badge(text, kind)


def gate_rows(evaluation) -> list[dict]:
    if not evaluation:
        return []
    return [
        {
            "Gate": gate.name,
            "Status": gate.status.value.upper(),
            "Justification": gate.justification,
        }
        for gate in evaluation.quality_gates
    ]


def score_rows(evaluation) -> list[dict]:
    if not evaluation:
        return []
    return [
        {
            "Criterion": score.name,
            "Weight": score.weight,
            "Score /10": score.score,
            "Weighted": score.weighted_score,
            "Justification": score.justification,
        }
        for score in evaluation.scores
    ]


def format_datetime(value) -> str:
    if not value:
        return "—"
    try:
        return value.strftime("%Y-%m-%d %H:%M")
    except AttributeError:
        return str(value)[:19]


def navigate_to(page_name: str) -> None:
    """Safely queue page navigation across canonical names and legacy aliases."""
    st.session_state["target_nav"] = page_name
    st.rerun()
