"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.database.connection import DatabaseConnection
from src.database.migrations import initialize_database
from src.database.repository import Repository


@pytest.fixture()
def repository(tmp_path: Path) -> Repository:
    db = DatabaseConnection(tmp_path / "test.db")
    initialize_database(db)
    repo = Repository(db)
    yield repo
    db.close()
