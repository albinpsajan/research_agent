"""General web connectors: RSS, Wikipedia, Hacker News, DuckDuckGo."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import feedparser

from config.logging_config import get_logger
from config.settings import get_settings
from src.research.base import ResearchError, SearchResult, query_terms
from src.research.http_client import ResearchHttpClient

logger = get_logger("research.web")


def _parse_feed_date(entry: dict) -> Optional[datetime]:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6])
        except (TypeError, ValueError):
            return None
    return None


class RSSConnector:
    """Configurable public RSS feeds, filtered by relevance when searching."""

    name = "rss"
    reliability = 0.62

    def __init__(self, http: Optional[ResearchHttpClient] = None) -> None:
        self.http = http or ResearchHttpClient()

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        terms = query_terms(query)
        results: list[SearchResult] = []
        for feed_url in get_settings().research.rss_feeds:
            try:
                cached = self.http.get(feed_url, ttl_hours=3)
            except ResearchError as exc:
                logger.warning("RSS feed failed %s: %s", feed_url, exc)
                continue
            feed = feedparser.parse(cached.text)
            feed_title = feed.feed.get("title", feed_url)
            for entry in feed.entries:
                title = " ".join(entry.get("title", "").split())
                summary = " ".join(entry.get("summary", "").split())
                haystack = f"{title} {summary}".lower()
                if terms and not any(term in haystack for term in terms):
                    continue
                link = entry.get("link", "")
                if not link:
                    continue
                results.append(
                    SearchResult(
                        title=title or "Untitled",
                        url=link,
                        snippet=summary[:700],
                        source_type="rss",
                        published_at=_parse_feed_date(entry),
                        metadata={"feed": feed_title, "feed_url": feed_url},
                        reliability=self.reliability,
                    )
                )
                if len(results) >= limit:
                    return results
        return results


class WikipediaConnector:
    """Wikipedia search API for organizer and domain background."""

    name = "wikipedia"
    reliability = 0.66

    def __init__(self, http: Optional[ResearchHttpClient] = None) -> None:
        self.http = http or ResearchHttpClient()

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        if not query.strip():
            return []
        try:
            payload = self.http.get_json(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query.strip()[:200],
                    "srlimit": max(1, min(limit, 10)),
                    "format": "json",
                    "utf8": 1,
                },
                ttl_hours=24,
            )
        except ResearchError as exc:
            logger.warning("Wikipedia search failed for %r: %s", query, exc)
            raise
        results: list[SearchResult] = []
        for item in (payload.get("query") or {}).get("search", []):
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            import re

            snippet = re.sub(r"<[^>]+>", "", snippet)
            results.append(
                SearchResult(
                    title=title,
                    url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                    snippet=snippet,
                    source_type="wikipedia",
                    metadata={"pageid": item.get("pageid")},
                    reliability=self.reliability,
                )
            )
        return results


class HackerNewsConnector:
    """Hacker News search via the free Algolia API (technology signals)."""

    name = "hackernews"
    reliability = 0.55

    def __init__(self, http: Optional[ResearchHttpClient] = None) -> None:
        self.http = http or ResearchHttpClient()

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        params = {
            "tags": "story",
            "hitsPerPage": max(1, min(limit, 20)),
        }
        if query.strip():
            params["query"] = query.strip()[:200]
            params["tags"] = "story"
        else:
            params["tags"] = "front_page"
        try:
            payload = self.http.get_json(
                "https://hn.algolia.com/api/v1/search",
                params=params,
                ttl_hours=6,
            )
        except ResearchError as exc:
            logger.warning("Hacker News search failed for %r: %s", query, exc)
            raise
        results: list[SearchResult] = []
        for hit in payload.get("hits", []):
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            results.append(
                SearchResult(
                    title=hit.get("title") or "Hacker News story",
                    url=url,
                    snippet=(
                        f"Points: {hit.get('points', 0)} | "
                        f"Comments: {hit.get('num_comments', 0)}"
                    ),
                    source_type="hackernews",
                    published_at=(
                        datetime.fromisoformat(hit["created_at"].replace("Z", "+00:00"))
                        if hit.get("created_at")
                        else None
                    ),
                    metadata={"hn_id": hit.get("objectID"), "points": hit.get("points", 0)},
                    reliability=self.reliability,
                )
            )
        return results


class DuckDuckGoConnector:
    """DuckDuckGo Instant Answer API (limited but key-free)."""

    name = "duckduckgo"
    reliability = 0.5

    def __init__(self, http: Optional[ResearchHttpClient] = None) -> None:
        self.http = http or ResearchHttpClient()

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        if not query.strip():
            return []
        try:
            payload = self.http.get_json(
                "https://api.duckduckgo.com/",
                params={
                    "q": query.strip()[:200],
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1,
                },
                ttl_hours=24,
            )
        except ResearchError as exc:
            logger.warning("DuckDuckGo search failed for %r: %s", query, exc)
            raise
        results: list[SearchResult] = []
        abstract = payload.get("AbstractText") or ""
        abstract_url = payload.get("AbstractURL") or ""
        if abstract and abstract_url:
            results.append(
                SearchResult(
                    title=payload.get("Heading") or query,
                    url=abstract_url,
                    snippet=abstract[:900],
                    source_type="duckduckgo",
                    metadata={"source": payload.get("AbstractSource")},
                    reliability=self.reliability,
                )
            )
        for topic in payload.get("RelatedTopics", []):
            if len(results) >= limit:
                break
            if "Topics" in topic:
                nested = topic.get("Topics", [])
            else:
                nested = [topic]
            for item in nested:
                if len(results) >= limit:
                    break
                url = item.get("FirstURL")
                text = item.get("Text")
                if url and text:
                    results.append(
                        SearchResult(
                            title=text.split(" - ")[0][:160],
                            url=url,
                            snippet=text[:700],
                            source_type="duckduckgo",
                            reliability=self.reliability,
                        )
                    )
        return results
