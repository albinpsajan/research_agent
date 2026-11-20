"""Shared Streamlit helpers and visual system."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.logging_config import setup_logging  # noqa: E402
from config.settings import get_settings  # noqa: E402
from src.database.migrations import initialize_database  # noqa: E402
from src.database.repository import Repository  # noqa: E402
from src.llm.client import OllamaClient  # noqa: E402

APP_VERSION = "1.0.0"


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
        :root {
            --ink: #e9edf2;
            --muted: #9aa7b8;
            --panel: rgba(20, 29, 43, 0.82);
            --panel-2: rgba(28, 39, 56, 0.75);
            --line: rgba(148, 163, 184, 0.18);
            --amber: #f5b942;
            --teal: #4fd1c5;
            --danger: #f87171;
            --ok: #6ee7a8;
        }
        .stApp {
            background:
                radial-gradient(1200px 600px at 15% -10%, rgba(79, 209, 197, 0.10), transparent 60%),
                radial-gradient(900px 500px at 95% 0%, rgba(245, 185, 66, 0.08), transparent 55%),
                linear-gradient(180deg, #0b1220 0%, #0d1524 45%, #0a101b 100%);
            color: var(--ink);
        }
        html, body, [class*="css"] { font-family: 'DM Sans', 'Segoe UI', sans-serif; }
        h1, h2, h3, h4 { font-family: 'Space Grotesk', 'Segoe UI', sans-serif; letter-spacing: -0.02em; }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(12, 19, 31, 0.98), rgba(15, 23, 38, 0.98));
            border-right: 1px solid var(--line);
        }
        .hiq-hero {
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 22px 26px;
            background: linear-gradient(135deg, rgba(24, 36, 54, 0.92), rgba(15, 23, 38, 0.72));
            box-shadow: 0 18px 50px rgba(0,0,0,0.25);
            margin-bottom: 18px;
        }
        .hiq-hero .eyebrow {
            color: var(--teal);
            text-transform: uppercase;
            letter-spacing: 0.16em;
            font-size: 0.72rem;
            font-weight: 700;
        }
        .hiq-hero h1 { margin: 6px 0 4px 0; font-size: 2.1rem; }
        .hiq-hero p { color: var(--muted); margin: 0; max-width: 900px; }
        .hiq-card {
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 18px 20px;
            background: var(--panel);
            margin-bottom: 14px;
        }
        .hiq-card h3 { margin-top: 0; }
        .hiq-winner {
            border: 1px solid rgba(245, 185, 66, 0.45);
            background: linear-gradient(135deg, rgba(245, 185, 66, 0.12), rgba(79, 209, 197, 0.06));
            border-radius: 18px;
            padding: 22px 24px;
        }
        .hiq-winner .label { color: var(--amber); text-transform: uppercase; letter-spacing: .14em; font-size: .72rem; font-weight: 700; }
        .hiq-winner h2 { margin: 6px 0 8px 0; }
        .hiq-pill {
            display: inline-block; padding: 3px 10px; border-radius: 999px;
            border: 1px solid var(--line); color: var(--muted); font-size: .78rem;
            margin-right: 6px; margin-bottom: 4px;
        }
        .hiq-pill.ok { color: var(--ok); border-color: rgba(110,231,168,.4); }
        .hiq-pill.bad { color: var(--danger); border-color: rgba(248,113,113,.4); }
        .hiq-pill.amber { color: var(--amber); border-color: rgba(245,185,66,.4); }
        .hiq-muted { color: var(--muted); }
        div[data-testid="stMetric"] {
            background: var(--panel-2);
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 12px 16px;
        }
        div[data-testid="stMetricLabel"] { color: var(--muted); }
        .stButton > button, .stDownloadButton > button {
            border-radius: 10px;
            border: 1px solid rgba(245,185,66,0.45);
            background: linear-gradient(180deg, rgba(245,185,66,0.18), rgba(245,185,66,0.08));
            color: #f7d99a;
            font-weight: 600;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            border-color: var(--amber); color: #fff2cf;
        }
        div[data-testid="stExpander"] {
            border: 1px solid var(--line);
            border-radius: 12px;
            background: rgba(16, 24, 38, 0.55);
        }
        .stTabs [data-baseweb="tab-list"] { gap: 6px; }
        .stTabs [data-baseweb="tab"] {
            background: rgba(20, 29, 43, 0.7);
            border: 1px solid var(--line);
            border-radius: 9px;
            padding: 8px 14px;
        }
        .stTabs [aria-selected="true"] {
            border-color: rgba(245,185,66,0.5);
            color: #f7d99a;
        }
        code { color: #9ee8df; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero(title: str, subtitle: str, eyebrow: str = "HackathonIQ") -> None:
    st.markdown(
        f"""
        <div class="hiq-hero">
            <div class="eyebrow">{eyebrow}</div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
            f"`{health.get('base_url')}`. Install Ollama for Windows, start it, "
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
    return f'<span class="hiq-pill {kind}">{text}</span>'


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
