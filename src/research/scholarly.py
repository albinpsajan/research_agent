"""Scholarly connectors: arXiv, OpenAlex and Crossref (free public APIs)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

import feedparser

from config.logging_config import get_logger
from config.settings import get_settings
from src.research.base import ResearchError, SearchResult
from src.research.http_client import ResearchHttpClient

logger = get_logger("research.scholarly")


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class ArxivConnector:
    """arXiv Atom API. No key required; rate limits apply."""

    name = "arxiv"
    reliability = 0.85

    def __init__(self, http: Optional[ResearchHttpClient] = None) -> None:
        self.http = http or ResearchHttpClient()

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        safe_query = re.sub(r'[^\w\s:\-\.]', " ", query).strip()
        if not safe_query:
            return []
        params = {
            "search_query": f"all:{safe_query}",
            "start": 0,
            "max_results": max(1, min(limit, 25)),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        request_url = "https://export.arxiv.org/api/query"
        try:
            cached = self.http.get(
                request_url
                + "?"
                + "&".join(f"{k}={httpx_quote(v)}" for k, v in params.items()),
                ttl_hours=24,
            )
        except ResearchError as exc:
            logger.warning("arXiv search failed for %r: %s", query, exc)
            raise
        feed = feedparser.parse(cached.text)
        results: list[SearchResult] = []
        for entry in feed.entries[:limit]:
            results.append(
                SearchResult(
                    title=" ".join(entry.get("title", "Untitled").split()),
                    url=entry.get("link", ""),
                    snippet=" ".join(entry.get("summary", "").split())[:900],
                    source_type="arxiv",
                    published_at=_parse_iso(entry.get("published")),
                    authors=[a.get("name", "") for a in entry.get("authors", [])][:8],
                    metadata={"arxiv_id": entry.get("id", "")},
                    reliability=self.reliability,
                )
            )
        return [r for r in results if r.url]


def httpx_quote(value: Any) -> str:
    from urllib.parse import quote_plus

    return quote_plus(str(value))


class OpenAlexConnector:
    """OpenAlex works API (free, polite pool via mailto)."""

    name = "openalex"
    reliability = 0.82

    def __init__(self, http: Optional[ResearchHttpClient] = None) -> None:
        self.http = http or ResearchHttpClient()
        self.contact_email = get_settings().research.contact_email

    @staticmethod
    def _abstract(inverted: Optional[dict[str, list[int]]]) -> str:
        if not inverted:
            return ""
        positions: list[tuple[int, str]] = []
        for word, indexes in inverted.items():
            for index in indexes:
                positions.append((index, word))
        positions.sort()
        return " ".join(word for _, word in positions)[:900]

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        if not query.strip():
            return []
        params = {
            "search": query.strip()[:200],
            "per-page": max(1, min(limit, 25)),
            "sort": "relevance_score:desc",
        }
        if self.contact_email:
            params["mailto"] = self.contact_email
        try:
            payload = self.http.get_json(
                "https://api.openalex.org/works",
                params=params,
                ttl_hours=24,
            )
        except ResearchError as exc:
            logger.warning("OpenAlex search failed for %r: %s", query, exc)
            raise
        results: list[SearchResult] = []
        for item in payload.get("results", []):
            title = item.get("display_name") or "Untitled work"
            url = item.get("doi") or item.get("id") or ""
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=self._abstract(item.get("abstract_inverted_index")),
                    source_type="openalex",
                    published_at=_parse_iso(item.get("publication_date")),
                    authors=[
                        a.get("author", {}).get("display_name", "")
                        for a in item.get("authorships", [])
                    ][:8],
                    metadata={
                        "cited_by_count": item.get("cited_by_count", 0),
                        "type": item.get("type"),
                        "open_access": (item.get("open_access") or {}).get("is_oa"),
                    },
                    reliability=self.reliability,
                )
            )
        return [r for r in results if r.url]


class CrossrefConnector:
    """Crossref works API for published research metadata."""

    name = "crossref"
    reliability = 0.78

    def __init__(self, http: Optional[ResearchHttpClient] = None) -> None:
        self.http = http or ResearchHttpClient()
        self.contact_email = get_settings().research.contact_email

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        if not query.strip():
            return []
        params = {
            "query": query.strip()[:200],
            "rows": max(1, min(limit, 20)),
            "select": "DOI,title,abstract,published,author,type,is-referenced-by-count",
        }
        if self.contact_email:
            params["mailto"] = self.contact_email
        try:
            payload = self.http.get_json(
                "https://api.crossref.org/works",
                params=params,
                ttl_hours=24,
            )
        except ResearchError as exc:
            logger.warning("Crossref search failed for %r: %s", query, exc)
            raise
        items = (payload.get("message") or {}).get("items", [])
        results: list[SearchResult] = []
        for item in items:
            titles = item.get("title") or ["Untitled"]
            doi = item.get("DOI")
            published = item.get("published", {}).get("date-parts", [[None]])
            date_value = None
            if published and published[0] and published[0][0]:
                parts = published[0]
                try:
                    date_value = datetime(
                        int(parts[0]),
                        int(parts[1]) if len(parts) > 1 else 1,
                        int(parts[2]) if len(parts) > 2 else 1,
                    )
                except (TypeError, ValueError):
                    date_value = None
            abstract = re.sub(r"<[^>]+>", " ", item.get("abstract") or "")
            results.append(
                SearchResult(
                    title=" ".join(str(titles[0]).split()),
                    url=f"https://doi.org/{doi}" if doi else "https://www.crossref.org/",
                    snippet=" ".join(abstract.split())[:900],
                    source_type="crossref",
                    published_at=date_value,
                    authors=[
                        f"{a.get('given', '')} {a.get('family', '')}".strip()
                        for a in item.get("author", [])
                    ][:8],
                    metadata={
                        "doi": doi,
                        "citations": item.get("is-referenced-by-count", 0),
                        "type": item.get("type"),
                    },
                    reliability=self.reliability,
                )
            )
        return results
