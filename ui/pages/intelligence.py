"""Continuous Global Intelligence Mode page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config.settings import get_settings
from src.intelligence.service import ContinuousIntelligenceService, load_sources_config
from ui.components.common import format_datetime, get_repository, hero


def render() -> None:
    settings = get_settings()
    repository = get_repository()
    service = ContinuousIntelligenceService(repository)
    hero(
        "Continuous global intelligence",
        "A local, provenance-tracked knowledge base of new research, repositories, "
        "products, technologies and problem signals. Reused in future hackathon runs "
        "with explicit freshness labels.",
        eyebrow="Mode B",
    )

    last = service.last_refresh()
    next_at = service.next_refresh_at()
    items = repository.intelligence_item_count()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stored signals", items)
    c2.metric("Last refresh", format_datetime(last))
    c3.metric("Next due", format_datetime(next_at) if next_at else "now")
    c4.metric("Interval", f"{settings.continuous_intelligence.refresh_interval_hours} h")

    st.caption(
        "The scheduler never polls continuously. Refresh happens only when the "
        "configured interval has elapsed, on a manual refresh, or via the CLI scheduler."
    )

    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("Refresh now", type="primary", use_container_width=True):
            with st.spinner("Collecting from GitHub, arXiv, OpenAlex, RSS and Hacker News…"):
                summary = service.refresh(force=True)
            if summary.total_items_new:
                st.success(
                    f"{summary.total_items_found} found, {summary.total_items_new} new."
                )
            else:
                st.info(
                    f"{summary.total_items_found} found, no new unique items. "
                    "Existing entries were de-duplicated by URL."
                )
            for result in summary.results:
                if result.status == "error":
                    st.warning(f"{result.source_type}: {result.error_message}")
            st.rerun()
    with c2:
        st.markdown(
            """
            **Scheduled refresh:** run the CLI scheduler in a separate terminal.
            ```powershell
            python -m src.cli scheduler --tick 300
            ```
            It checks whether the interval has elapsed every five minutes and performs
            no network collection when it is not due.
            """
        )

    st.markdown("### Knowledge base")
    categories = ["All"] + sorted(
        {
            row["category"]
            for row in repository.list_intelligence_items(limit=500)
            if row.get("category")
        }
    )
    category = st.selectbox("Category", categories)
    rows = repository.list_intelligence_items(
        limit=200, category=None if category == "All" else category
    )
    if rows:
        frame = pd.DataFrame(
            [
                {
                    "Title": row.get("title", ""),
                    "Source": row.get("source_type", ""),
                    "Category": row.get("category", ""),
                    "Freshness": format_datetime(row.get("freshness_date")),
                    "Stale": bool(row.get("is_stale")),
                    "URL": row.get("url") or "",
                }
                for row in rows
            ]
        )
        st.dataframe(
            frame,
            use_container_width=True,
            hide_index=True,
            column_config={
                "URL": st.column_config.LinkColumn("URL", display_text="Open"),
            },
        )
    else:
        st.info("The knowledge base is empty. Run a refresh.")

    st.markdown("### Theme relevance lookup")
    theme = st.text_input(
        "Check what the knowledge base already knows about a theme",
        placeholder="e.g. climate resilience for coastal cities",
    )
    if theme.strip():
        context = service.context_for_theme(theme)
        st.caption(context.note)
        if context.items:
            st.markdown(
                "\n".join(
                    f"- **{item.title}** ({item.source_type}, "
                    f"{format_datetime(item.freshness_date or item.retrieved_at)}) "
                    + (f"[link]({item.url})" if item.url else "")
                    for item in context.items[:20]
                )
            )

    st.markdown("### Source configuration")
    config = load_sources_config()
    st.json(config, expanded=False)
    st.caption(
        "Edit `config/intelligence_sources.json` to add or remove watch topics. "
        "RSS feeds are configured in `config/settings.py` and can be overridden "
        "through environment variables."
    )

    st.markdown("### Refresh history")
    history = repository.refresh_history(limit=30)
    if history:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Source": row.get("source_type"),
                        "Found": row.get("items_found"),
                        "New": row.get("items_new"),
                        "Status": row.get("status"),
                        "Started": format_datetime(row.get("started_at")),
                        "Error": row.get("error_message") or "",
                    }
                    for row in history
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No refresh has run yet.")
