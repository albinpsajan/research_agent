"""Deadline arithmetic shared by feasibility and evaluation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from config.settings import get_settings

if TYPE_CHECKING:
    from src.models.hackathon import HackathonInput


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)


def available_hours(hackathon: HackathonInput) -> float:
    """Hours until the deadline, or the documented 36-hour default."""
    if not hackathon.deadline:
        return get_settings().agent.default_hackathon_hours
    now = datetime.now(UTC)
    deadline = hackathon.deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    return max((deadline - now).total_seconds() / 3600, 0.0)


def deadline_is_explicit(hackathon: HackathonInput) -> bool:
    return hackathon.deadline is not None


def deadline_note(hackathon: HackathonInput) -> str:
    hours = available_hours(hackathon)
    if not hackathon.deadline:
        return (
            f"No deadline supplied; a documented default of {hours:.0f} hours was "
            "assumed for feasibility checks."
        )
    return f"{hours:.1f} hours remain until the supplied deadline."
