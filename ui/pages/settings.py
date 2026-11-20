"""Settings: local model, storage budget, research defaults."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config.settings import get_settings, reset_settings, save_user_settings
from src.storage.manager import StorageManager
from ui.components.common import get_llm, hero, reset_caches


def render() -> None:
    settings = get_settings()
    storage = StorageManager()
    storage.ensure_dirs()
    hero(
        "Settings",
        "Local-first by design. No paid AI subscription is required; the only large "
        "download is the local Ollama model, and it is guarded by a storage check.",
        eyebrow="Configuration",
    )

    health = get_llm().health()
    st.markdown("### Local model")
    c1, c2, c3 = st.columns(3)
    c1.metric("Ollama", "online" if health.get("available") else "offline")
    c2.metric("Active model", health.get("active_model") or settings.ollama.model)
    c3.metric("Installed models", len(health.get("models", [])))
    if not health.get("available"):
        st.error(
            f"Ollama is not reachable at `{health.get('base_url')}`. Install it with "
            "`winget install Ollama.Ollama`, start the Ollama app, then refresh."
        )
    elif health.get("models"):
        st.caption("Installed: " + ", ".join(f"`{name}`" for name in health["models"]))

    with st.form("model_settings"):
        st.markdown("#### Model configuration")
        c1, c2 = st.columns(2)
        with c1:
            model = st.text_input("Primary model", value=settings.ollama.model)
            num_ctx = st.number_input(
                "Context window (tokens)",
                min_value=2048,
                max_value=32768,
                value=settings.ollama.num_ctx,
                step=1024,
            )
            temperature = st.slider(
                "Temperature", 0.0, 1.0, float(settings.ollama.temperature), 0.05
            )
        with c2:
            fallback = st.text_input(
                "Fallback model", value=settings.ollama.fallback_model
            )
            timeout = st.number_input(
                "Request timeout (seconds)",
                min_value=30,
                max_value=1800,
                value=settings.ollama.timeout,
                step=30,
            )
        if st.form_submit_button("Save model settings", type="primary"):
            save_user_settings(
                {
                    "ollama": {
                        "model": model.strip(),
                        "fallback_model": fallback.strip(),
                        "num_ctx": int(num_ctx),
                        "temperature": float(temperature),
                        "timeout": int(timeout),
                    }
                }
            )
            reset_settings()
            reset_caches()
            st.success("Model settings saved.")
            st.rerun()

    st.markdown("#### Download a model")
    st.caption(
        "The recommended starting model for a 6 GB RTX 3050 is `qwen2.5:7b` "
        "(4-bit, roughly 4.7 GB). `qwen2.5:3b` is a lighter fallback. "
        "HackathonIQ never downloads automatically."
    )
    model_to_pull = st.text_input(
        "Model to pull", value=settings.ollama.model, key="pull_model_name"
    )
    estimated = 5.0 if "7b" in model_to_pull.lower() else 2.2
    report = storage.get_storage_report()
    st.caption(
        f"Estimated download: {estimated:.1f} GB · budget used "
        f"{report.used_gb:.2f}/{report.budget_gb:.1f} GB · "
        f"{report.disk_free_gb:.1f} GB free on disk"
    )
    if st.button("Check space and download", use_container_width=False):
        allowed, reason = storage.check_before_download(estimated)
        if not allowed:
            st.error(reason)
        elif not health.get("available"):
            st.error("Start Ollama first.")
        else:
            with st.spinner(f"Pulling {model_to_pull}. This can take several minutes…"):
                try:
                    get_llm().pull_model(model_to_pull)
                    reset_caches()
                    st.success(f"Model ready: {model_to_pull}")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001 - show real error
                    st.error(f"Download failed: {exc}")

    st.markdown("### Storage protection")
    report = storage.get_storage_report()
    c1, c2, c3 = st.columns(3)
    c1.metric("Budget used", f"{report.used_gb:.2f} GB")
    c2.metric("Budget", f"{report.budget_gb:.1f} GB")
    c3.metric("Disk free", f"{report.disk_free_gb:.1f} GB")
    if report.categories:
        st.bar_chart(
            pd.DataFrame(
                [{"Category": key, "GB": value} for key, value in report.categories.items()]
            ).set_index("Category")
        )
    for warning in report.warnings:
        st.warning(warning)
    st.caption(
        "The 30 GB budget is a guard-rail, not an allocation. Cache cleanup only "
        "touches HackathonIQ's own cache directory and never personal files."
    )
    with st.form("storage_settings"):
        c1, c2 = st.columns(2)
        with c1:
            budget = st.number_input(
                "Storage budget (GB)",
                min_value=1.0,
                max_value=500.0,
                value=float(settings.storage.budget_gb),
                step=1.0,
            )
        with c2:
            warn = st.slider(
                "Warn at fraction of budget",
                0.5,
                1.0,
                float(settings.storage.warn_threshold),
                0.05,
            )
        if st.form_submit_button("Save storage settings"):
            save_user_settings(
                {"storage": {"budget_gb": float(budget), "warn_threshold": float(warn)}}
            )
            reset_settings()
            reset_caches()
            st.success("Storage settings saved.")
            st.rerun()

    with st.expander("Safe cache cleanup"):
        days = st.number_input(
            "Delete HackathonIQ cache files older than (days)",
            min_value=1,
            max_value=365,
            value=7,
        )
        confirm = st.checkbox(
            "I understand this only deletes files inside data/cache."
        )
        if st.button("Run cache cleanup", disabled=not confirm):
            removed = storage.cleanup_cache(int(days))
            st.success(f"Removed {removed} cache file(s). Personal files were untouched.")

    st.markdown("### Research defaults")
    with st.form("agent_settings"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            max_domains = st.number_input(
                "Max domains", 3, 20, settings.agent.max_domains
            )
        with c2:
            per_domain = st.number_input(
                "Problems per domain", 1, 5, settings.agent.problems_per_domain
            )
        with c3:
            finalists = st.number_input(
                "Finalists", 2, 10, settings.agent.max_finalists
            )
        with c4:
            rounds = st.number_input(
                "Debate rounds", 1, 5, settings.agent.max_debate_rounds
            )
        refresh_hours = st.number_input(
            "Continuous Intelligence interval (hours)",
            min_value=1,
            max_value=720,
            value=settings.continuous_intelligence.refresh_interval_hours,
        )
        if st.form_submit_button("Save research defaults"):
            save_user_settings(
                {
                    "agent": {
                        "max_domains": int(max_domains),
                        "problems_per_domain": int(per_domain),
                        "max_finalists": int(finalists),
                        "max_debate_rounds": int(rounds),
                    },
                    "continuous_intelligence": {
                        "refresh_interval_hours": int(refresh_hours)
                    },
                }
            )
            reset_settings()
            reset_caches()
            st.success("Research defaults saved.")
            st.rerun()

    st.markdown("### Privacy and cost")
    st.markdown(
        """
        - All inference runs locally through Ollama. No prompts or findings are sent
          to a paid AI API.
        - Research requests go directly to public APIs and websites (GitHub, arXiv,
          OpenAlex, Crossref, Wikipedia, Hacker News, RSS feeds, and URLs you supply).
        - Optional `GITHUB_TOKEN` raises GitHub's unauthenticated rate limit; it is
          read from the environment or `.env` and never displayed.
        - Public APIs may rate-limit or be temporarily unavailable. Failures are
          recorded and reported rather than hidden.
        - The database, reports, cache and logs stay under `data/`.
        """
    )
