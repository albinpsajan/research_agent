"""HackathonIQ command-line interface.

Examples:
    python -m src.cli check
    python -m src.cli research --theme "Sustainable cities" --name "CityHack"
    python -m src.cli intelligence-refresh
    python -m src.cli scheduler
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from config.logging_config import setup_logging
from config.settings import get_settings
from src.database.migrations import initialize_database
from src.database.repository import Repository
from src.intelligence.service import ContinuousIntelligenceService
from src.llm.client import LLMError, OllamaClient
from src.models.hackathon import HackathonInput
from src.models.pipeline import PipelineOptions
from src.orchestration.pipeline import HackathonPipeline
from src.storage.manager import StorageManager
from src.utils.hackathon_time import utc_now


def _progress(stage: str, message: str, fraction: float) -> None:
    print(f"[{fraction:>5.0%}] {stage}: {message}", flush=True)


def cmd_check(_: argparse.Namespace) -> int:
    settings = get_settings()
    storage = StorageManager()
    storage.ensure_dirs()
    report = storage.get_storage_report()
    llm = OllamaClient()
    health = llm.health()
    print("HackathonIQ environment check")
    print(f"  Database: {settings.db_path}")
    print(f"  Ollama:   {health.get('base_url')} available={health.get('available')}")
    print(f"  Models:   {', '.join(health.get('models', [])) or 'none'}")
    print(
        f"  Storage:  {report.used_gb:.2f} GB used of {report.budget_gb:.1f} GB budget; "
        f"{report.disk_free_gb:.1f} GB free on disk"
    )
    for warning in report.warnings:
        print(f"  WARNING: {warning}")
    if not health.get("available"):
        print("  ACTION: install/start Ollama, then run `ollama pull qwen2.5:7b`.")
        return 1
    if not health.get("models"):
        print("  ACTION: no models installed. Run `python -m src.cli pull-model`.")
        return 1
    return 0


def cmd_init_db(_: argparse.Namespace) -> int:
    db = Repository().db
    initialize_database(db)
    print(f"Database initialized at {db.db_path}")
    return 0


def cmd_pull_model(args: argparse.Namespace) -> int:
    settings = get_settings()
    model = args.model or settings.ollama.model
    estimated = 5.0 if "7b" in model.lower() else 2.2
    storage = StorageManager()
    allowed, reason = storage.check_before_download(estimated)
    if not allowed:
        print(f"Refused: {reason}")
        return 1
    llm = OllamaClient()
    try:
        llm.pull_model(model)
    except LLMError as exc:
        print(f"Model pull failed: {exc}")
        return 1
    print(f"Model ready: {model}")
    return 0


def cmd_research(args: argparse.Namespace) -> int:
    deadline = None
    if args.deadline:
        try:
            deadline = datetime.fromisoformat(args.deadline)
        except ValueError:
            print("Deadline must be ISO-8601, e.g. 2026-12-01T18:00")
            return 2
    hackathon = HackathonInput(
        theme=args.theme,
        name=args.name,
        website_url=args.website,
        rules_url=args.rules,
        deadline=deadline,
        constraints=args.constraints,
    )
    options = PipelineOptions(
        max_domains=args.max_domains,
        problems_per_domain=args.problems_per_domain,
        max_finalists=args.finalists,
        max_debate_rounds=args.debate_rounds,
        include_continuous_intelligence=not args.no_ci,
    )
    pipeline = HackathonPipeline(progress=_progress)
    result = pipeline.run(hackathon, options)
    if result.status == "failed":
        print(f"\nFAILED: {result.error}")
        return 1
    if result.winner and result.winner.has_winner and result.winner.winner:
        print(
            f"\nWINNER: {result.winner.winner.candidate_title} "
            f"({result.winner.winner.total_score:.1f}/100)"
        )
    else:
        print(
            "\nNO WINNER: "
            + (
                result.winner.rejection_reason
                if result.winner and result.winner.rejection_reason
                else "no candidate qualified"
            )
        )
    if result.report:
        path = (
            Path(get_settings().storage.reports_dir)
            / f"{result.report.metadata.report_id}.md"
        )
        print(f"Report: {path}")
    print(f"Session: {result.session_id}")
    if args.json_out:
        Path(args.json_out).write_text(
            result.model_dump_json(indent=2), encoding="utf-8"
        )
        print(f"JSON: {args.json_out}")
    return 0


def cmd_intelligence_refresh(args: argparse.Namespace) -> int:
    service = ContinuousIntelligenceService()
    summary = service.refresh(force=not args.only_if_due)
    if summary.skipped:
        print(f"Skipped: {summary.skip_reason}")
        return 0
    print(
        f"Refresh complete: {summary.total_items_found} found, "
        f"{summary.total_items_new} new"
    )
    for result in summary.results:
        print(
            f"  {result.source_type}: found={result.items_found} "
            f"new={result.items_new} status={result.status}"
            + (f" error={result.error_message}" if result.error_message else "")
        )
    return 0


def cmd_scheduler(args: argparse.Namespace) -> int:
    service = ContinuousIntelligenceService()
    tick = max(args.tick, 30)
    print(f"Scheduler started; tick={tick}s. Ctrl+C to stop.")
    try:
        while True:
            summary = service.run_if_due()
            if summary.skipped:
                print(f"{utc_now().isoformat()} — {summary.skip_reason}", flush=True)
            else:
                print(
                    f"{utc_now().isoformat()} — refreshed "
                    f"{summary.total_items_new} new item(s)",
                    flush=True,
                )
            time.sleep(tick)
    except KeyboardInterrupt:
        print("Scheduler stopped.")
        return 0


def cmd_report(args: argparse.Namespace) -> int:
    from src.orchestration.loader import load_session_result

    result = load_session_result(args.session_id)
    if not result:
        print("Session not found.")
        return 1
    if not result.report:
        print("This session has no persisted report.")
        return 1
    if args.out:
        Path(args.out).write_text(result.report.to_markdown(), encoding="utf-8")
        print(f"Report written to {args.out}")
    else:
        print(result.report.to_markdown())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hackathoniq",
        description="Autonomous multi-agent hackathon intelligence system",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Check Ollama, storage and database")
    check.set_defaults(func=cmd_check)

    init_db = sub.add_parser("init-db", help="Initialize the SQLite database")
    init_db.set_defaults(func=cmd_init_db)

    pull = sub.add_parser("pull-model", help="Pull the configured Ollama model")
    pull.add_argument("--model", default=None)
    pull.set_defaults(func=cmd_pull_model)

    research = sub.add_parser("research", help="Run a complete research workflow")
    research.add_argument("--theme", required=True)
    research.add_argument("--name", default=None)
    research.add_argument("--website", default=None)
    research.add_argument("--rules", default=None)
    research.add_argument("--deadline", default=None, help="ISO-8601 datetime")
    research.add_argument("--constraints", default=None)
    research.add_argument("--max-domains", type=int, default=8)
    research.add_argument("--problems-per-domain", type=int, default=2)
    research.add_argument("--finalists", type=int, default=5)
    research.add_argument("--debate-rounds", type=int, default=3)
    research.add_argument("--no-ci", action="store_true")
    research.add_argument("--json-out", default=None)
    research.set_defaults(func=cmd_research)

    refresh = sub.add_parser("intelligence-refresh", help="Refresh global intelligence")
    refresh.add_argument("--only-if-due", action="store_true")
    refresh.set_defaults(func=cmd_intelligence_refresh)

    scheduler = sub.add_parser("scheduler", help="Run the refresh scheduler loop")
    scheduler.add_argument("--tick", type=int, default=300)
    scheduler.set_defaults(func=cmd_scheduler)

    report = sub.add_parser("report", help="Export a persisted report")
    report.add_argument("--session-id", required=True)
    report.add_argument("--out", default=None)
    report.set_defaults(func=cmd_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
