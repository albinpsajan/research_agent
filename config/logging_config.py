"""Logging configuration for HackathonIQ."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from config.settings import get_settings


def setup_logging(settings: object | None = None) -> None:
    """Configure the root *hackathoniq* logger.

    Adds a console handler (always) and a file handler when the log-file
    path is set in settings.
    """
    if settings is None:
        settings = get_settings()

    log_cfg = settings.logging
    root_logger = logging.getLogger("hackathoniq")
    root_logger.setLevel(getattr(logging, log_cfg.level.upper(), logging.INFO))

    # Avoid duplicate handlers on repeated calls
    if root_logger.handlers:
        return

    formatter = logging.Formatter(log_cfg.format)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    # File handler (optional)
    if log_cfg.log_file:
        log_path = Path(log_cfg.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the *hackathoniq* namespace."""
    return logging.getLogger(f"hackathoniq.{name}")
