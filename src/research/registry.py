"""Connector registry and source-tracking research service."""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone

from config.logging_config import get_logger
from config.settings import get_settings
from src.database.repository import Repository
from src.models.research import GitHubProject
from src.research.base import PageContent, ResearchError, SearchResult
from src.research.github import GitHubConnector
from src.research.http_client import ResearchHttpClient
from src.research.scholarly import ArxivConnector, CrossrefConnector, OpenAlexConnector
from src.research.web import (
    DuckDuckGoConnector,
    HackerNewsConnector,
    RSSConnector,
    WikipediaConnector,
)

logger = get_logger("research.registry")

ALL_SOURCE_TYPES = (
    "github",
    "arxiv",
    "openalex",
    "crossref",
    "rss",
    "wikipedia",
    "hackernews",
    "duckduckgo",
)


def _safe_timestamp(dt: datetime | None) -> float:
    """Safely convert datetime to epoch seconds on all platforms (avoiding Windows pre-1970 OSError)."""
    if dt is None:
        return 0.0
    try:
        if dt.tzinfo is not None:
            return (dt - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()
        return (dt - datetime(1970, 1, 1)).total_seconds()
    except Exception:
        return 0.0


@dataclass
class SearchBundle:
    """Results plus per-source errors, so partial failure is transparent."""

    query: str
    results: list[SearchResult] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    queries: list[str] = field(default_factory=list)

    def extend(self, other: SearchBundle) -> None:
        self.results.extend(other.results)
        self.errors.update(other.errors)
        self.queries.extend(other.queries)

    def dedupe(self) -> None:
        seen: set[str] = set()
        unique: list[SearchResult] = []
        for result in self.results:
            key = (result.url or result.title).rstrip("/").lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(result)
        self.results = unique

    def as_context(self, max_items: int = 30, max_chars: int = 14000) -> str:
        """Numbered evidence context; IDs are stable for this prompt only."""
        lines: list[str] = []
        for index, result in enumerate(self.results[:max_items], start=1):
            lines.append(result.as_context(index))
        text = "\n\n".join(lines)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...[context truncated]"
        return text


class ConnectorRegistry:
    """Runs reusable connectors with bounded concurrency."""

    def __init__(
        self,
        http: ResearchHttpClient | None = None,
        connectors: dict[str, object] | None = None,
    ) -> None:
        self.http = http or ResearchHttpClient()
        self.connectors = connectors or {
            "github": GitHubConnector(self.http),
            "arxiv": ArxivConnector(self.http),
            "openalex": OpenAlexConnector(self.http),
            "crossref": CrossrefConnector(self.http),
            "rss": RSSConnector(self.http),
            "wikipedia": WikipediaConnector(self.http),
            "hackernews": HackerNewsConnector(self.http),
            "duckduckgo": DuckDuckGoConnector(self.http),
        }

    def search(
        self,
        query: str,
        *,
        source_types: Iterable[str] | None = None,
        limit: int = 8,
    ) -> SearchBundle:
        selected = list(source_types or ALL_SOURCE_TYPES)
        bundle = SearchBundle(query=query, queries=[query])
        if not query.strip():
            return bundle
        workers = min(len(selected), 8)
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {
                pool.submit(self.connectors[name].search, query, limit): name
                for name in selected
                if name in self.connectors
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results = future.result()
                    bundle.results.extend(results)
                except ResearchError as exc:
                    bundle.errors[name] = str(exc)
                    logger.warning("Connector %s failed: %s", name, exc)
                except Exception as exc:
                    bundle.errors[name] = f"Unexpected error: {exc}"
                    logger.exception("Connector %s crashed", name)
        # Prefer richer sources first, then recency.
        bundle.results.sort(
            key=lambda r: (
                -r.reliability,
                -_safe_timestamp(r.published_at),
            )
        )
        bundle.dedupe()
        return bundle

    def multi_search(
        self,
        queries: list[str],
        *,
        source_types: Iterable[str] | None = None,
        limit: int = 6,
        max_results: int = 30,
    ) -> SearchBundle:
        combined = SearchBundle(query="; ".join(queries))
        for query in queries:
            combined.extend(self.search(query, source_types=source_types, limit=limit))
        combined.dedupe()
        combined.results = combined.results[:max_results]
        return combined


class ResearchService:
    """Facade used by agents: searches, fetches pages and records provenance."""

    def __init__(
        self,
        repository: Repository | None = None,
        registry: ConnectorRegistry | None = None,
    ) -> None:
        self.repository = repository or Repository()
        self.registry = registry or ConnectorRegistry()
        self.http = self.registry.http
        self.settings = get_settings()

    def record_source(self, session_id: str | None, result: SearchResult) -> None:
        if not result.url:
            return
        self.repository.save_research_source(
            session_id=session_id,
            url=result.url,
            title=result.title,
            source_type=result.source_type,
            description=result.snippet[:1500],
            metadata=result.metadata,
            reliability=result.reliability,
        )

    def search(
        self,
        session_id: str | None,
        query: str,
        *,
        source_types: Iterable[str] | None = None,
        limit: int | None = None,
    ) -> SearchBundle:
        bundle = self.registry.search(
            query,
            source_types=source_types,
            limit=limit or self.settings.agent.research_results_per_query,
        )
        for result in bundle.results:
            self.record_source(session_id, result)
        return bundle

    def multi_search(
        self,
        session_id: str | None,
        queries: list[str],
        *,
        source_types: Iterable[str] | None = None,
        limit: int = 6,
        max_results: int = 30,
    ) -> SearchBundle:
        bundle = self.registry.multi_search(
            queries,
            source_types=source_types,
            limit=limit,
            max_results=max_results,
        )
        for result in bundle.results:
            self.record_source(session_id, result)
        return bundle

    def fetch_page(self, session_id: str | None, url: str) -> PageContent:
        page = self.http.fetch_page(url)
        self.repository.save_research_source(
            session_id=session_id,
            url=page.final_url,
            title=page.title or page.final_url,
            source_type="web",
            description=page.text[:1500],
            metadata={"requested_url": url},
            reliability=0.8,
        )
        return page

    def github_projects(
        self, session_id: str | None, query: str, limit: int = 8
    ) -> list[GitHubProject]:
        bundle = self.search(session_id, query, source_types=["github"], limit=limit)
        projects: list[GitHubProject] = []
        for result in bundle.results:
            metadata = result.metadata
            updated = metadata.get("updated_at")
            projects.append(
                GitHubProject(
                    url=result.url,
                    name=result.title,
                    description=metadata.get("description") or result.snippet,
                    stars=int(metadata.get("stars", 0) or 0),
                    forks=int(metadata.get("forks", 0) or 0),
                    language=metadata.get("language"),
                    last_updated=(datetime.fromisoformat(updated) if updated else None),
                    topics=metadata.get("topics", []),
                    is_active=not bool(metadata.get("archived")),
                    documentation_quality=(
                        "described" if metadata.get("description") else "minimal"
                    ),
                    functionality_summary=result.snippet,
                )
            )
        return projects

    def close(self) -> None:
        """Close underlying HTTP clients and release resources."""
        if hasattr(self, "http") and hasattr(self.http, "close"):
            try:
                self.http.close()
            except Exception:
                pass
