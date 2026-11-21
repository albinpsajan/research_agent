"""Continuous Global Intelligence Mode.

Refreshes a local knowledge base from public sources on a configurable
schedule, stores provenance, and reuses relevant findings in new hackathon
runs with explicit freshness labels.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from config.logging_config import get_logger
from config.settings import get_settings
from src.database.repository import Repository
from src.models.intelligence import (
    IntelligenceContext,
    IntelligenceItem,
    RefreshResult,
    RefreshSummary,
)
from src.research.base import ResearchError, SearchResult, query_terms
from src.research.github import GitHubConnector
from src.research.scholarly import ArxivConnector, OpenAlexConnector
from src.research.web import HackerNewsConnector, RSSConnector
from src.utils.hackathon_time import utc_now

logger = get_logger("intelligence")

SOURCES_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "config"
    / "intelligence_sources.json"
)


def load_sources_config() -> dict[str, Any]:
    try:
        payload = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not read %s; using empty watch list", SOURCES_PATH)
        return {}


class ContinuousIntelligenceService:
    """Collects, stores and retrieves global innovation signals."""

    def __init__(
        self,
        repository: Repository | None = None,
        *,
        github: GitHubConnector | None = None,
        arxiv: ArxivConnector | None = None,
        openalex: OpenAlexConnector | None = None,
        rss: RSSConnector | None = None,
        hackernews: HackerNewsConnector | None = None,
    ) -> None:
        self.repository = repository or Repository()
        self.settings = get_settings()
        self.sources = load_sources_config()
        self.github = github or GitHubConnector()
        self.arxiv = arxiv or ArxivConnector()
        self.openalex = openalex or OpenAlexConnector()
        self.rss = rss or RSSConnector()
        self.hackernews = hackernews or HackerNewsConnector()

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def last_refresh(self) -> datetime | None:
        row = self.repository.get_last_refresh()
        if not row:
            return None
        raw = row.get("completed_at") or row.get("started_at")
        try:
            dt = datetime.fromisoformat(str(raw))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except (ValueError, TypeError):
            return None

    def is_due(self) -> bool:
        if not self.settings.continuous_intelligence.enabled:
            return False
        last = self.last_refresh()
        if last is None:
            return True
        return utc_now() - last >= timedelta(
            hours=self.settings.continuous_intelligence.refresh_interval_hours
        )

    def next_refresh_at(self) -> datetime | None:
        last = self.last_refresh()
        if last is None:
            return None
        return last + timedelta(
            hours=self.settings.continuous_intelligence.refresh_interval_hours
        )

    def run_if_due(self) -> RefreshSummary:
        if not self.is_due():
            return RefreshSummary(
                skipped=True,
                skip_reason=(f"Not due yet. Next refresh at {self.next_refresh_at()}."),
            )
        return self.refresh(force=False)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self, force: bool = True) -> RefreshSummary:
        if not force and not self.is_due():
            return RefreshSummary(
                skipped=True, skip_reason="Refresh interval not elapsed."
            )
        summary = RefreshSummary()
        collectors = [
            ("github", self._collect_github),
            ("arxiv", self._collect_arxiv),
            ("openalex", self._collect_openalex),
            ("rss", self._collect_rss),
            ("hackernews", self._collect_hackernews),
        ]
        for source_type, collector in collectors:
            started = utc_now()
            try:
                results = collector()
                new_count = 0
                for result in results:
                    item_id = self._store(result)
                    if item_id is not None:
                        new_count += 1
                summary.results.append(
                    RefreshResult(
                        source_type=source_type,
                        items_found=len(results),
                        items_new=new_count,
                        status="success",
                        started_at=started,
                        completed_at=utc_now(),
                    )
                )
                self.repository.log_refresh(
                    source_type, len(results), new_count, "success", None
                )
            except Exception as exc:  # noqa: BLE001 - isolate source failure
                logger.warning("Intelligence source %s failed: %s", source_type, exc)
                summary.results.append(
                    RefreshResult(
                        source_type=source_type,
                        status="error",
                        error_message=str(exc)[:500],
                        started_at=started,
                        completed_at=utc_now(),
                    )
                )
                self.repository.log_refresh(source_type, 0, 0, "error", str(exc)[:500])
        stale = self.repository.mark_stale_intelligence(
            self.settings.continuous_intelligence.stale_after_days
        )
        if stale:
            logger.info("Marked %s intelligence item(s) stale", stale)
        summary.finalize()
        return summary

    def _store(self, result: SearchResult, category: str | None = None) -> int | None:
        topics = query_terms(f"{result.title} {result.snippet}", limit=8)

        text = f"{result.title} {result.snippet}".lower()
        if "kerala" in text or any(d in text for d in ["wayanad", "kuttanad", "idukki", "palakkad", "alappuzha"]):
            geography = "kerala"
        elif "india" in text or "indian" in text:
            geography = "india"
        else:
            geography = "global"

        if any(w in text for w in ["agriculture", "crop", "farm", "agro", "monsoon"]):
            domain = "agriculture"
        elif any(w in text for w in ["health", "medical", "disease", "telemedicine", "dengue"]):
            domain = "healthcare"
        elif any(w in text for w in ["education", "school", "learning", "vernacular"]):
            domain = "education"
        elif any(w in text for w in ["disaster", "flood", "landslide", "hazard"]):
            domain = "disaster_management"
        else:
            domain = "general"

        metadata = dict(result.metadata)
        metadata.update(
            {
                "authors": result.authors,
                "reliability": result.reliability,
                "domain": domain,
                "geography": geography,
                "published_at": (
                    result.published_at.isoformat() if result.published_at else None
                ),
            }
        )
        return self.repository.save_intelligence_item(
            source_type=result.source_type,
            category=category or self._category(result.source_type),
            title=result.title[:400],
            description=result.snippet[:2000],
            url=result.url or None,
            metadata=metadata,
            topics=topics,
            freshness_date=(
                result.published_at.isoformat()
                if result.published_at
                else utc_now().isoformat()
            ),
        )

    @staticmethod
    def _category(source_type: str) -> str:
        return {
            "github": "repository",
            "arxiv": "research",
            "openalex": "research",
            "rss": "news",
            "hackernews": "technology_signal",
        }.get(source_type, "news")

    # ------------------------------------------------------------------
    # Collectors (bounded)
    # ------------------------------------------------------------------

    def _collect_github(self) -> list[SearchResult]:
        results: list[SearchResult] = []
        errors: list[str] = []
        limit = self.settings.continuous_intelligence.max_items_per_source
        since = (utc_now() - timedelta(days=45)).strftime("%Y-%m-%d")
        for topic in self.sources.get("github_topics", [])[:8]:
            query = f"topic:{topic} pushed:>{since}"
            try:
                found = self.github.search(query, limit=min(6, limit))
            except ResearchError as exc:
                logger.warning("GitHub intelligence topic %s failed: %s", topic, exc)
                errors.append(str(exc))
                continue
            for result in found:
                result.metadata["watch_topic"] = topic
                results.append(result)
        if not results and errors:
            raise ResearchError(f"All GitHub intelligence queries failed: {errors[-1]}")
        return results[:limit]

    def _collect_arxiv(self) -> list[SearchResult]:
        results: list[SearchResult] = []
        errors: list[str] = []
        limit = self.settings.continuous_intelligence.max_items_per_source
        for query in self.sources.get("arxiv_queries", [])[:6]:
            try:
                found = self.arxiv.search(query, limit=min(5, limit))
            except ResearchError as exc:
                logger.warning("arXiv intelligence query %s failed: %s", query, exc)
                errors.append(str(exc))
                continue
            for result in found:
                result.metadata["watch_topic"] = query
                results.append(result)
        if not results and errors:
            raise ResearchError(f"All arXiv intelligence queries failed: {errors[-1]}")
        return results[:limit]

    def _collect_openalex(self) -> list[SearchResult]:
        results: list[SearchResult] = []
        errors: list[str] = []
        limit = self.settings.continuous_intelligence.max_items_per_source
        for query in self.sources.get("openalex_queries", [])[:5]:
            try:
                found = self.openalex.search(query, limit=min(5, limit))
            except ResearchError as exc:
                logger.warning("OpenAlex intelligence query %s failed: %s", query, exc)
                errors.append(str(exc))
                continue
            for result in found:
                result.metadata["watch_topic"] = query
                results.append(result)
        if not results and errors:
            raise ResearchError(
                f"All OpenAlex intelligence queries failed: {errors[-1]}"
            )
        return results[:limit]

    def _collect_rss(self) -> list[SearchResult]:
        limit = self.settings.continuous_intelligence.max_items_per_source
        return self.rss.search("", limit=min(limit, 30))

    def _collect_hackernews(self) -> list[SearchResult]:
        limit = self.settings.continuous_intelligence.max_items_per_source
        results = self.hackernews.search("", limit=min(limit, 30))
        for result in results:
            result.metadata["signal_type"] = (
                "product_launch"
                if "show hn" in result.title.lower()
                else "technology_signal"
            )
        return results

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def context_for_theme(
        self, theme: str, extra_terms: list[str] | None = None, limit: int = 20
    ) -> IntelligenceContext:
        terms = query_terms(theme, limit=6) + [
            term for term in (extra_terms or []) if term
        ]
        rows = self.repository.search_intelligence_items(terms, limit=limit)
        items = []
        for row in rows:
            meta = row.get("metadata_json") or {}
            items.append(
                IntelligenceItem(
                    id=row.get("id"),
                    source_type=row.get("source_type", ""),
                    category=row.get("category", ""),
                    title=row.get("title", ""),
                    description=row.get("description"),
                    url=row.get("url"),
                    domain=meta.get("domain", "general"),
                    geography=meta.get("geography", "global"),
                    reliability=float(meta.get("reliability", 0.8)),
                    publication_date=_parse_datetime(meta.get("published_at")) if meta.get("published_at") else None,
                    topics=row.get("topics_json") or [],
                    metadata=meta,
                    retrieved_at=_parse_datetime(row.get("retrieved_at")),
                    freshness_date=_parse_datetime(row.get("freshness_date")),
                    is_stale=bool(row.get("is_stale")),
                )
            )
        dates = [item.freshness_date or item.retrieved_at for item in items]
        dates = [date for date in dates if date]
        newest = max(dates) if dates else None
        oldest = min(dates) if dates else None
        note = (
            f"{len(items)} relevant stored signal(s); newest {newest.date().isoformat() if newest else 'unknown'}."
            if items
            else "No relevant stored intelligence yet; run a Continuous Intelligence refresh."
        )
        return IntelligenceContext(
            items=items,
            newest_item_at=newest,
            oldest_item_at=oldest,
            matched_topics=terms,
            note=note,
        )

    def context_as_prompt(
        self, context: IntelligenceContext, max_items: int = 10
    ) -> str:
        if not context.items:
            return ""
        lines = [f"Freshness: {context.note}"]
        for item in context.items[:max_items]:
            date = (item.freshness_date or item.retrieved_at).date().isoformat()
            lines.append(
                f"- [{item.source_type}/{item.category}, {date}] {item.title}"
                f"{' — ' + item.url if item.url else ''}\n  {(item.description or '')[:240]}"
            )
        return "\n".join(lines)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return utc_now()
