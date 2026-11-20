"""Models for Continuous Global Intelligence Mode."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.utils.hackathon_time import utc_now


class IntelligenceItem(BaseModel):
    """A single tracked discovery from a public source."""

    id: int | None = None
    source_type: str
    category: str
    title: str
    description: str | None = None
    url: str | None = None
    topics: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieved_at: datetime = Field(default_factory=utc_now)
    freshness_date: datetime | None = None
    is_stale: bool = False


class RefreshResult(BaseModel):
    """Outcome of refreshing one intelligence source."""

    source_type: str
    items_found: int = 0
    items_new: int = 0
    status: str = "success"  # success | error | skipped
    error_message: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class RefreshSummary(BaseModel):
    """Aggregated outcome of a Continuous Intelligence refresh."""

    results: list[RefreshResult] = Field(default_factory=list)
    total_items_found: int = 0
    total_items_new: int = 0
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    skipped: bool = False
    skip_reason: str | None = None

    def finalize(self) -> None:
        self.total_items_found = sum(r.items_found for r in self.results)
        self.total_items_new = sum(r.items_new for r in self.results)
        self.completed_at = utc_now()


class IntelligenceContext(BaseModel):
    """Freshness-labelled context injected into a hackathon research run."""

    items: list[IntelligenceItem] = Field(default_factory=list)
    newest_item_at: datetime | None = None
    oldest_item_at: datetime | None = None
    matched_topics: list[str] = Field(default_factory=list)
    note: str = ""
