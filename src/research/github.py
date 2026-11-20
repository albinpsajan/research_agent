"""GitHub repository research connector with rate-limit monitoring, query optimization, and caching."""

from __future__ import annotations

import re
import time
from datetime import datetime

from config.logging_config import get_logger
from config.settings import ResearchSettings, get_settings
from src.research.base import ResearchError, SearchResult
from src.research.http_client import ResearchHttpClient

logger = get_logger("research.github")

STOP_WORDS = {
    "how", "many", "entries", "recent", "hackathons", "academic", "papers",
    "propose", "what", "are", "the", "distinguishing", "features", "this",
    "proposal", "compared", "others", "there", "about", "using", "with",
    "and", "for", "from", "that", "which", "would", "could", "should",
    "existing", "solution", "solutions", "project", "projects", "open", "source",
    "system", "systems", "platform", "platforms", "tool", "tools",
}


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def optimize_github_query(raw_query: str) -> str:
    """Transform conversational or lengthy queries into concise, high-signal repository search tokens."""
    cleaned = re.sub(r"[^\w\s\-]", " ", raw_query)
    tokens = [w for w in cleaned.lower().split() if len(w) > 2 and w not in STOP_WORDS]
    if not tokens:
        tokens = [w for w in cleaned.lower().split() if len(w) > 2][:4]
    optimized = " ".join(tokens[:5]).strip()[:80]
    return optimized or "agriculture"


class GitHubConnector:
    """Search real public repositories through the GitHub REST API."""

    name = "github"
    reliability = 0.78
    _query_cache: dict[str, list[SearchResult]] = {}
    _rate_limited_until: float = 0.0

    def __init__(
        self,
        http: ResearchHttpClient | None = None,
        settings: ResearchSettings | None = None,
    ) -> None:
        self.settings = settings or get_settings().research
        self.http = http or ResearchHttpClient(self.settings)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        return headers

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        cleaned_query = optimize_github_query(query)
        if not cleaned_query:
            return []

        # Check in-memory query cache
        if cleaned_query in self._query_cache:
            return self._query_cache[cleaned_query][:limit]

        # Check if currently cooling down from rate limit
        now = time.time()
        if now < self._rate_limited_until:
            logger.info(
                "GitHub API rate limit cooldown active (%.0fs remaining); serving cached repositories.",
                self._rate_limited_until - now,
            )
            # Return any previously cached results matching tokens
            tokens = set(cleaned_query.split())
            matching: list[SearchResult] = []
            for cached_q, items in self._query_cache.items():
                if tokens & set(cached_q.split()):
                    matching.extend(items)
            return matching[:limit]

        params = {
            "q": cleaned_query,
            "sort": "stars",
            "order": "desc",
            "per_page": max(1, min(limit, 30)),
        }
        try:
            payload = self.http.get_json(
                "https://api.github.com/search/repositories",
                params=params,
                ttl_hours=6,
                headers=self._headers(),
            )
        except ResearchError as exc:
            err_msg = str(exc)
            if "403" in err_msg or "429" in err_msg or "rate limit" in err_msg.lower():
                self._rate_limited_until = time.time() + 90.0
                logger.warning(
                    "GitHub API rate limit encountered. Cooldown initiated for 90s. Error: %s",
                    exc,
                )
            else:
                logger.warning("GitHub search failed for %r (%r): %s", query, cleaned_query, exc)
            return []

        items = payload.get("items", [])
        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        for item in items:
            html_url = item.get("html_url", "")
            if not html_url or html_url in seen_urls:
                continue
            seen_urls.add(html_url)

            description = (item.get("description") or "").strip()
            topics = item.get("topics") or []
            stars = item.get("stargazers_count", 0)
            forks = item.get("forks_count", 0)
            lang = item.get("language") or "unknown"
            updated = (item.get("updated_at") or "")[:10]

            snippet_parts = [description or "No description provided"]
            if topics:
                snippet_parts.append("Topics: " + ", ".join(topics[:6]))
            snippet_parts.append(f"Stars: {stars} | Forks: {forks} | Language: {lang} | Updated: {updated}")
            if item.get("archived"):
                snippet_parts.append("ARCHIVED repository")

            # Relevance boost: active repos with stars and documentation
            repo_reliability = min(0.90, self.reliability + (0.1 if stars > 10 else 0.0) + (0.05 if not item.get("archived") else -0.1))

            results.append(
                SearchResult(
                    title=item.get("full_name") or item.get("name", "Repository"),
                    url=html_url,
                    snippet=" | ".join(snippet_parts),
                    source_type="github",
                    publication_category="software_project",
                    verification_level="metadata_validated",
                    published_at=_parse_date(item.get("created_at")),
                    metadata={
                        "stars": stars,
                        "forks": forks,
                        "language": lang,
                        "updated_at": item.get("updated_at"),
                        "topics": topics,
                        "archived": bool(item.get("archived")),
                        "open_issues": item.get("open_issues_count", 0),
                        "description": description,
                        "license": (item.get("license") or {}).get("spdx_id"),
                    },
                    reliability=round(repo_reliability, 2),
                )
            )

        self._query_cache[cleaned_query] = results
        return results[:limit]

    def readme_excerpt(self, full_name: str, max_chars: int = 1500) -> str:
        """Fetch a repository README when available (used for documentation QA)."""
        if time.time() < self._rate_limited_until:
            return ""
        try:
            payload = self.http.get_json(
                f"https://api.github.com/repos/{full_name}/readme",
                ttl_hours=24,
                headers=self._headers(),
            )
        except ResearchError:
            return ""
        import base64
        content = payload.get("content", "")
        if not content:
            return ""
        try:
            decoded = base64.b64decode(content).decode("utf-8", errors="replace")
            return " ".join(decoded.split())[:max_chars]
        except Exception:
            return ""
