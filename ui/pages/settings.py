"""Settings page: Local model, storage protection, research parameters, and system preferences."""

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
    health = get_llm().health()

    hero(
        "Platform Configuration & Local Settings",
        "Local-first by design. All LLM inference runs 100% locally through Ollama with zero paid AI subscriptions. "
        "Storage budgets and cache limits guard disk health.",
        eyebrow="Configuration",
        badge_text="Local Engine",
    )

    tab_llm, tab_storage, tab_research, tab_privacy = st.tabs([
        "🤖 Local LLM Engine",
        "💾 Storage Protection & Quota",
        "⚙️ Research Parameters",
        "🔒 Privacy & Rate Limits",
    ])

    # -------------------------------------------------------------
    # TAB 1: LOCAL LLM ENGINE
    # -------------------------------------------------------------
    with tab_llm:
        st.markdown("### Local Model Telemetry")
        c1, c2, c3 = st.columns(3)
        c1.metric("Ollama Engine", "Online" if health.get("available") else "Offline")
        c2.metric("Active Model", (health.get("active_model") or settings.ollama.model).split(":")[0])
        c3.metric("Installed Models", len(health.get("models", [])))

        if not health.get("available"):
            st.error(
                f"Ollama is not reachable at `{health.get('base_url')}`. Start the Ollama application, then refresh."
            )
        elif health.get("models"):
            st.caption("Installed models: " + ", ".join(f"`{name}`" for name in health["models"]))

        with st.form("model_settings_form"):
            st.markdown("#### LLM Inference Parameters")
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                model = st.text_input("Primary Model Name", value=settings.ollama.model)
                num_ctx = st.number_input(
                    "Context Window (tokens)",
                    min_value=2048,
                    max_value=32768,
                    value=settings.ollama.num_ctx,
                    step=1024,
                )
                temperature = st.slider(
                    "Temperature", 0.0, 1.0, float(settings.ollama.temperature), 0.05
                )
            with col_m2:
                fallback = st.text_input(
                    "Fallback Model", value=settings.ollama.fallback_model
                )
                timeout = st.number_input(
                    "Inference Timeout (seconds)",
                    min_value=30,
                    max_value=1800,
                    value=settings.ollama.timeout,
                    step=30,
                )

            if st.form_submit_button("Save Model Configuration", type="primary"):
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
                st.success("Model configuration saved successfully.")
                st.rerun()

        st.markdown("#### Download / Pull Model")
        st.caption(
            "Recommended model for 6 GB RTX 3050 is `qwen2.5:7b` (4-bit, ~4.7 GB). "
            "`qwen2.5:3b` is a lighter fallback. HackathonIQ never downloads models without a storage pre-check."
        )
        model_to_pull = st.text_input("Model Name to Pull", value=settings.ollama.model, key="pull_model_input")
        estimated = 5.0 if "7b" in model_to_pull.lower() else 2.2
        storage_rep = storage.get_storage_report()
        st.caption(
            f"Estimated size: {estimated:.1f} GB · Budget used: {storage_rep.used_gb:.2f} / {storage_rep.budget_gb:.1f} GB · "
            f"Disk free: {storage_rep.disk_free_gb:.1f} GB"
        )
        if st.button("Check Disk Space & Download Model"):
            allowed, reason = storage.check_before_download(estimated)
            if not allowed:
                st.error(reason)
            elif not health.get("available"):
                st.error("Start Ollama service first.")
            else:
                with st.spinner(f"Pulling `{model_to_pull}` from Ollama library..."):
                    try:
                        get_llm().pull_model(model_to_pull)
                        reset_caches()
                        st.success(f"Model ready: {model_to_pull}")
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Download failed: {exc}")

    # -------------------------------------------------------------
    # TAB 2: STORAGE PROTECTION & QUOTA
    # -------------------------------------------------------------
    with tab_storage:
        st.markdown("### Storage Budget & Usage")
        rep = storage.get_storage_report()
        s1, s2, s3 = st.columns(3)
        s1.metric("Budget Used", f"{rep.used_gb:.2f} GB")
        s2.metric("Storage Budget", f"{rep.budget_gb:.1f} GB")
        s3.metric("Disk Free Space", f"{rep.disk_free_gb:.1f} GB")

        if rep.categories:
            st.bar_chart(
                pd.DataFrame([{"Category": k, "GB": v} for k, v in rep.categories.items()]).set_index("Category")
            )
        for w in rep.warnings:
            st.warning(w)

        with st.form("storage_budget_form"):
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                budget = st.number_input(
                    "Storage Budget Guardrail (GB)",
                    min_value=1.0,
                    max_value=500.0,
                    value=float(settings.storage.budget_gb),
                    step=1.0,
                )
            with col_b2:
                warn_thresh = st.slider(
                    "Warning Threshold Fraction",
                    0.5,
                    1.0,
                    float(settings.storage.warn_threshold),
                    0.05,
                )
            if st.form_submit_button("Update Storage Guardrails"):
                save_user_settings(
                    {"storage": {"budget_gb": float(budget), "warn_threshold": float(warn_thresh)}}
                )
                reset_settings()
                reset_caches()
                st.success("Storage guardrails updated.")
                st.rerun()

        with st.expander("Safe Cache Cleanup"):
            days = st.number_input("Delete cache entries older than (days)", min_value=1, max_value=365, value=7)
            confirm = st.checkbox("I understand this only cleans temporary data inside data/cache.")
            if st.button("Run Safe Cache Cleanup", disabled=not confirm):
                removed = storage.cleanup_cache(int(days))
                st.success(f"Removed {removed} temporary cache file(s). Database and reports were untouched.")

    # -------------------------------------------------------------
    # TAB 3: RESEARCH PARAMETERS
    # -------------------------------------------------------------
    with tab_research:
        st.markdown("### Default Research Pipeline Tuning")
        with st.form("research_parameters_form"):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                max_d = st.number_input("Max Domains to Explore", 3, 20, settings.agent.max_domains)
            with c2:
                p_per_d = st.number_input("Problems per Domain", 1, 5, settings.agent.problems_per_domain)
            with c3:
                fin_cnt = st.number_input("Finalist Candidates", 2, 10, settings.agent.max_finalists)
            with c4:
                deb_rnd = st.number_input("Debate Rounds", 1, 5, settings.agent.max_debate_rounds)

            ci_hours = st.number_input(
                "Continuous Intelligence Refresh Interval (hours)",
                min_value=1,
                max_value=720,
                value=settings.continuous_intelligence.refresh_interval_hours,
            )

            if st.form_submit_button("Save Research Defaults", type="primary"):
                save_user_settings(
                    {
                        "agent": {
                            "max_domains": int(max_d),
                            "problems_per_domain": int(p_per_d),
                            "max_finalists": int(fin_cnt),
                            "max_debate_rounds": int(deb_rnd),
                        },
                        "continuous_intelligence": {
                            "refresh_interval_hours": int(ci_hours),
                        },
                    }
                )
                reset_settings()
                reset_caches()
                st.success("Research default parameters saved.")
                st.rerun()

    # -------------------------------------------------------------
    # TAB 4: PRIVACY & RATE LIMITS
    # -------------------------------------------------------------
    with tab_privacy:
        st.markdown("### Privacy Architecture & Cost Guarantees")
        st.markdown(
            """
            - **100% Local Inference:** All model inferences run on your local hardware via Ollama. No hackathon ideas, problem statements, or prompts are sent to external LLM APIs.
            - **Direct Public Retrieval:** Ground-truth research requests query authoritative public endpoints (GitHub, arXiv, OpenAlex, Crossref, Wikipedia, Hacker News, RSS feeds, Kerala/India open portals).
            - **No Paid API Keys Required:** Zero subscriptions or paywalls are necessary. An optional `GITHUB_TOKEN` environment variable may be supplied to elevate GitHub's unauthenticated rate limits.
            - **Local SQLite Persistence:** All research databases, raw agent telemetry, extracted document chunks, and Markdown reports remain strictly within `data/`.
            """
        )
