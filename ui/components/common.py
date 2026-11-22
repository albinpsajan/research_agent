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

APP_VERSION = "2.0.0"

# Canonical page name mappings for backward compatibility
PAGE_ALIASES: dict[str, str] = {
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
}


def inject_css() -> None:
    """Inject HackathonIQ dark theme design system CSS."""
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
            --line-strong: rgba(148, 163, 184, 0.24);

            /* Typography */
            --text-primary: #f8fafc;
            --text-muted: #94a3b8;
            --text-subdued: #64748b;

            /* Brand & Accent Tokens */
            --teal: #0d9488;
            --teal-bright: #14b8a6;
            --teal-subtle: rgba(13, 148, 136, 0.15);
            --gold: #f59e0b;
            --gold-bright: #fbbf24;
            --gold-subtle: rgba(245, 158, 11, 0.14);

            /* Status Signals */
            --ok: #10b981;
            --ok-subtle: rgba(16, 185, 129, 0.14);
            --danger: #ef4444;
            --danger-subtle: rgba(239, 68, 68, 0.14);
            --warn: #f59e0b;
            --warn-subtle: rgba(245, 158, 11, 0.14);
            --info: #38bdf8;
            --info-subtle: rgba(56, 189, 248, 0.14);

            /* Radii & Shadows */
            --radius-sm: 6px;
            --radius-md: 10px;
            --radius-lg: 14px;
            --radius-xl: 18px;
            --shadow-subtle: 0 4px 12px rgba(0, 0, 0, 0.35);
        }

        /* Base Streamlit Overrides */
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

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: #0d131f;
            border-right: 1px solid var(--line);
        }

        section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
            gap: 0.6rem;
        }

        /* Professional Header Card */
        .hiq-hero {
            border: 1px solid var(--line);
            border-radius: var(--radius-lg);
            padding: 22px 26px;
            background: linear-gradient(145deg, #111827 0%, #0d1422 100%);
            box-shadow: var(--shadow-subtle);
            margin-bottom: 20px;
            position: relative;
        }

        .hiq-hero .eyebrow {
            color: var(--teal-bright);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.72rem;
            font-weight: 700;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .hiq-hero h1 {
            margin: 0 0 6px 0;
            font-size: 1.85rem;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: -0.025em;
        }

        .hiq-hero p {
            color: var(--text-muted);
            margin: 0;
            font-size: 0.95rem;
            line-height: 1.55;
            max-width: 960px;
        }

        /* Standard Surface Card */
        .hiq-card {
            border: 1px solid var(--line);
            border-radius: var(--radius-md);
            padding: 18px 22px;
            background-color: var(--panel);
            margin-bottom: 16px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        }

        .hiq-card-elevated {
            border: 1px solid var(--line-strong);
            border-radius: var(--radius-md);
            padding: 20px 24px;
            background-color: var(--panel-elevated);
            margin-bottom: 16px;
        }

        /* Executive Winner Card */
        .hiq-winner {
            border: 1px solid rgba(245, 158, 11, 0.4);
            background: linear-gradient(145deg, rgba(245, 158, 11, 0.08) 0%, rgba(13, 148, 136, 0.04) 100%), #111827;
            border-radius: var(--radius-lg);
            padding: 24px 28px;
            margin-bottom: 22px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
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

        /* Status Pills & Badges */
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

        .hiq-pill.info {
            color: var(--info);
            background: var(--info-subtle);
            border-color: rgba(56, 189, 248, 0.3);
        }

        /* Professional Metric Boxes */
        div[data-testid="stMetric"] {
            background-color: var(--panel);
            border: 1px solid var(--line);
            border-radius: var(--radius-md);
            padding: 14px 18px;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
        }

        div[data-testid="stMetricLabel"] {
            color: var(--text-muted);
            font-size: 0.82rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }

        div[data-testid="stMetricValue"] {
            color: #ffffff;
            font-size: 1.55rem;
            font-weight: 700;
            letter-spacing: -0.02em;
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
            box-shadow: 0 2px 6px rgba(13, 148, 136, 0.25);
        }

        .stButton > button[kind="primary"]:hover, .stButton > button[type="primary"]:hover {
            background: linear-gradient(180deg, #14b8a6 0%, #0d9488 100%);
            border-color: #2dd4bf;
            color: #ffffff;
            box-shadow: 0 4px 12px rgba(20, 184, 166, 0.35);
        }

        /* Secondary / Default Buttons */
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

        /* Form Inputs & Selectboxes */
        div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] {
            border-radius: var(--radius-sm) !important;
            background-color: #0c131f !important;
            border-color: var(--line-strong) !important;
        }

        /* Tabs — Crisp Modern Outline */
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
            border-bottom: 1px solid var(--line);
            padding-bottom: 4px;
            margin-bottom: 16px;
        }

        .stTabs [data-baseweb="tab"] {
            background: transparent;
            border: none;
            border-radius: var(--radius-sm);
            padding: 8px 14px;
            color: var(--text-muted);
            font-weight: 500;
            font-size: 0.9rem;
            transition: all 0.12s ease;
        }

        .stTabs [data-baseweb="tab"]:hover {
            color: var(--text-primary);
            background: rgba(255, 255, 255, 0.03);
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

        /* Dataframes & Tables */
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--line);
            border-radius: var(--radius-md);
            overflow: hidden;
        }

        /* Code & Monospace */
        code {
            font-family: 'JetBrains Mono', Consolas, monospace;
            color: #5eead4;
            background-color: rgba(13, 148, 136, 0.12);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.88em;
        }

        /* Agent Pipeline Cards */
        .hiq-agent-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            margin: 16px 0;
        }

        .hiq-agent-card {
            border: 1px solid var(--line);
            border-radius: var(--radius-md);
            padding: 14px 16px;
            background: var(--panel);
            transition: border-color 0.15s ease;
        }

        .hiq-agent-card.running {
            border-color: var(--teal);
            background: linear-gradient(145deg, rgba(13, 148, 136, 0.08), var(--panel));
        }

        .hiq-agent-card.completed {
            border-color: rgba(16, 185, 129, 0.4);
        }

        /* Empty State */
        .hiq-empty {
            border: 1px dashed var(--line-strong);
            border-radius: var(--radius-lg);
            padding: 42px 30px;
            text-align: center;
            background-color: rgba(17, 24, 39, 0.4);
            margin: 20px 0;
        }
        .hiq-empty h3 { margin: 8px 0 4px 0; color: #ffffff; }
        .hiq-empty p { color: var(--text-muted); font-size: 0.92rem; max-width: 520px; margin: 0 auto 16px auto; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero(title: str, subtitle: str, eyebrow: str = "HackathonIQ", badge_text: str | None = None) -> None:
    """Render a consistent, clean page hero header."""
    badge_html = f'<span class="hiq-pill teal" style="margin-left:8px;">{badge_text}</span>' if badge_text else ""
    st.markdown(
        f"""
        <div class="hiq-hero">
            <div class="eyebrow">{eyebrow}{badge_html}</div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(
    title: str,
    subtitle: str,
    eyebrow: str = "HackathonIQ",
    badge_text: str | None = None,
) -> None:
    """Alias for hero with identical contract."""
    hero(title, subtitle, eyebrow=eyebrow, badge_text=badge_text)


def empty_state(
    title: str,
    description: str,
    icon: str = "◈",
    cta_label: str | None = None,
    cta_page: str | None = None,
) -> None:
    """Render a reassuring empty state with optional primary navigation CTA."""
    st.markdown(
        f"""
        <div class="hiq-empty">
            <div style="font-size: 2.2rem; color: #94a3b8; margin-bottom: 4px;">{icon}</div>
            <h3>{title}</h3>
            <p>{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if cta_label and cta_page:
        col_pad1, col_btn, col_pad2 = st.columns([2, 1, 2])
        with col_btn:
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
            "Ollama is not reachable at "
            f"`{health.get('base_url')}`. Start Ollama on your system, "
            "then refresh this page."
        )
        st.code("winget install Ollama.Ollama\nollama pull qwen2.5:7b", language="powershell")
    elif not health.get("models"):
        st.warning(
            "Ollama is running but no model is installed. Use **Settings → Model** "
            "to download the configured model (disk space is checked first)."
        )
    return health


def badge(text: str, kind: str = "") -> str:
    """Return an HTML status badge string."""
    return f'<span class="hiq-pill {kind}">{text}</span>'


def status_pill(text: str, kind: str = "") -> str:
    """Alias for badge."""
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
