"""Smoke tests for importable UI and CLI entry points."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ui_modules_import() -> None:
    import ui.components.common
    import ui.pages.documents
    import ui.pages.history
    import ui.pages.intelligence
    import ui.pages.new_research
    import ui.pages.playbook
    import ui.pages.results
    import ui.pages.settings

    assert all(
        [
            ui.components.common,
            ui.pages.documents,
            ui.pages.history,
            ui.pages.intelligence,
            ui.pages.new_research,
            ui.pages.playbook,
            ui.pages.results,
            ui.pages.settings,
        ]
    )


def test_cli_help_runs() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "src.cli", "--help"],
        check=False,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0
    assert "research" in completed.stdout
    assert "intelligence-refresh" in completed.stdout
