"""Storage budget and safe cleanup tests."""

from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace

from src.storage.manager import StorageManager


def _manager(tmp_path: Path, budget: float = 1.0) -> StorageManager:
    storage = SimpleNamespace(
        budget_gb=budget,
        warn_threshold=0.8,
        models_dir=tmp_path / "models",
        cache_dir=tmp_path / "cache",
        reports_dir=tmp_path / "reports",
        logs_dir=tmp_path / "logs",
        db_path=tmp_path / "db.sqlite",
    )
    return StorageManager(SimpleNamespace(storage=storage))


def test_report_and_budget_warning(tmp_path: Path) -> None:
    manager = _manager(tmp_path, budget=0.0005)
    manager.ensure_dirs()
    (tmp_path / "cache" / "big.bin").write_bytes(b"x" * (1024 * 1024))
    report = manager.get_storage_report()
    assert report.used_gb > 0
    assert report.usage_fraction > 0.8
    assert report.warnings


def test_download_guard_blocks_budget_and_disk(tmp_path: Path) -> None:
    manager = _manager(tmp_path, budget=0.001)
    allowed, reason = manager.check_before_download(1.0)
    assert not allowed
    assert "exceed" in reason.lower() or "budget" in reason.lower()


def test_cleanup_only_touches_cache(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    manager.ensure_dirs()
    old_cache = tmp_path / "cache" / "old.txt"
    old_cache.write_text("cache", encoding="utf-8")
    personal = tmp_path / "models" / "keep.txt"
    personal.write_text("keep", encoding="utf-8")
    past = time.time() - 10 * 86_400
    os.utime(old_cache, (past, past))
    os.utime(personal, (past, past))
    removed = manager.cleanup_cache(max_age_days=7)
    assert removed == 1
    assert not old_cache.exists()
    assert personal.exists()
