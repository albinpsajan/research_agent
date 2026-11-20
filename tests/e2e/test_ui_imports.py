"""Smoke tests for importable UI and CLI entry points."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ui_modules_import() -> None:
    import ui.components.common  # noqa: F401
    import ui.pages.history  # noqa: F401
    import ui.pages.intelligence  # noqa: F401
    import ui.pages.new_research  # noqa: F401
    import ui.pages.results  # noqa: F401
    import ui.pages.settings  # noqa: F401


def test_cli_help_runs() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "src.cli", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0
    assert "research" in completed.stdout
    assert "intelligence-refresh" in completed.stdout
