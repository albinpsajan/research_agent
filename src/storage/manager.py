"""Storage manager – disk-budget tracking and cache cleanup."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from pydantic import BaseModel, Field

from config.settings import get_settings


class StorageReport(BaseModel):
    """Snapshot of current storage usage."""

    budget_gb: float
    used_gb: float
    free_gb: float
    usage_fraction: float
    disk_free_gb: float
    categories: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class StorageManager:
    """Manages disk-budget tracking, directory creation, and cache cleanup."""

    def __init__(self, settings: object | None = None) -> None:
        self._settings = settings or get_settings()
        self._storage = self._settings.storage

    # ------------------------------------------------------------------
    # Directory helpers
    # ------------------------------------------------------------------

    def ensure_dirs(self) -> None:
        """Create all configured data directories if they don't exist."""
        dirs = [
            self._storage.models_dir,
            self._storage.cache_dir,
            self._storage.reports_dir,
            self._storage.logs_dir,
        ]
        uploads = getattr(self._storage, "uploads_dir", None)
        if uploads:
            dirs.append(uploads)

        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Size helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_directory_size_gb(path: Path) -> float:
        """Return the total size of *path* in GiB (0.0 if missing)."""
        if not path.exists():
            return 0.0
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return total / (1024**3)

    @staticmethod
    def get_disk_free_gb(path: Path | None = None) -> float:
        """Return free disk space in GiB for the volume containing *path*."""
        target = Path(path or ".")
        # A not-yet-created application directory still belongs to a volume;
        # walk up to the nearest existing parent instead of failing.
        while not target.exists() and target != target.parent:
            target = target.parent
        usage = shutil.disk_usage(str(target))
        return usage.free / (1024**3)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_storage_report(self) -> StorageReport:
        """Build a comprehensive storage report."""
        categories: dict[str, float] = {
            "models": self.get_directory_size_gb(Path(self._storage.models_dir)),
            "cache": self.get_directory_size_gb(Path(self._storage.cache_dir)),
            "reports": self.get_directory_size_gb(Path(self._storage.reports_dir)),
            "logs": self.get_directory_size_gb(Path(self._storage.logs_dir)),
        }
        uploads = getattr(self._storage, "uploads_dir", None)
        if uploads:
            categories["uploads"] = self.get_directory_size_gb(Path(uploads))

        used_gb = sum(categories.values())
        budget_gb = self._storage.budget_gb
        free_gb = max(budget_gb - used_gb, 0.0)
        usage_fraction = used_gb / budget_gb if budget_gb > 0 else 0.0
        disk_free_gb = self.get_disk_free_gb(Path(self._storage.models_dir))

        warnings: list[str] = []
        if usage_fraction >= self._storage.warn_threshold:
            warnings.append(
                f"Storage usage at {usage_fraction:.0%} of budget "
                f"({used_gb:.2f}/{budget_gb:.1f} GB)"
            )
        if disk_free_gb < 5.0:
            warnings.append(
                f"Low disk space: only {disk_free_gb:.1f} GB free on volume"
            )

        return StorageReport(
            budget_gb=budget_gb,
            used_gb=round(used_gb, 4),
            free_gb=round(free_gb, 4),
            usage_fraction=round(usage_fraction, 4),
            disk_free_gb=round(disk_free_gb, 2),
            categories=categories,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Download guard
    # ------------------------------------------------------------------

    def check_before_download(self, size_gb: float) -> tuple[bool, str]:
        """Return (allowed, reason) for a prospective download of *size_gb*."""
        report = self.get_storage_report()
        new_usage = report.used_gb + size_gb
        if new_usage > report.budget_gb:
            return (
                False,
                (
                    f"Download of {size_gb:.2f} GB would exceed budget "
                    f"({new_usage:.2f}/{report.budget_gb:.1f} GB). "
                    "Free up space or increase the budget."
                ),
            )
        if size_gb > report.disk_free_gb:
            return (
                False,
                (
                    f"Download of {size_gb:.2f} GB exceeds available disk space "
                    f"({report.disk_free_gb:.1f} GB free)."
                ),
            )
        return (True, "OK")

    # ------------------------------------------------------------------
    # Cache cleanup  (only touches the cache directory – never personal files)
    # ------------------------------------------------------------------

    def cleanup_cache(self, max_age_days: int = 7) -> int:
        """Delete cache files older than *max_age_days*.

        Only operates on the configured cache directory.  Returns the
        number of files removed.
        """
        cache_dir = Path(self._storage.cache_dir)
        if not cache_dir.exists():
            return 0

        cutoff = time.time() - (max_age_days * 86_400)
        removed = 0
        for file in cache_dir.rglob("*"):
            if file.is_file() and file.stat().st_mtime < cutoff:
                file.unlink()
                removed += 1
        return removed
