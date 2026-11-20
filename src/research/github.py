"""GitHub repository research connector."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from config.logging_config import get_logger
from config.settings import ResearchSettings, get_settings
from src.research.base import ResearchError, SearchResult
from src.research.http_client import ResearchHttpClient

logger = get_logger("research.github")


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GitHubConnector:
    """Search real public repositories through the GitHub REST API."""

    name = "github"
    reliability = 0.78

    def __init__(
        self,
        http: Optional[ResearchHttpClient] = None,
        settings: Optional[ResearchSettings] = None,
    ) -> None:
        self.settings = settings or get_settings().research
        self.http = http or ResearchHttpClient(self.settings)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        return headers

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        if not query.strip():
            return []
        params = {
            "q": query.strip()[:240],
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
            logger.warning("GitHub search failed for %r: %s", query, exc)
            raise
        items = payload.get("items", [])
        results: list[SearchResult] = []
        for item in items:
            description = (item.get("description") or "").strip()
            topics = item.get("topics") or []
            snippet_parts = [description or "No description"]
            if topics:
                snippet_parts.append("Topics: " + ", ".join(topics[:8]))
            snippet_parts.append(
                f"Stars: {item.get('stargazers_count', 0)} | "
                f"Forks: {item.get('forks_count', 0)} | "
                f"Language: {item.get('language') or 'unknown'} | "
                f"Updated: {(item.get('updated_at') or '')[:10]}"
            )
            if item.get("archived"):
                snippet_parts.append("ARCHIVED repository")
            results.append(
                SearchResult(
                    title=item.get("full_name") or item.get("name", "Repository"),
                    url=item.get("html_url", ""),
                    snippet=" | ".join(snippet_parts),
                    source_type="github",
                    published_at=_parse_date(item.get("created_at")),
                    metadata={
                        "stars": item.get("stargazers_count", 0),
                        "forks": item.get("forks_count", 0),
                        "language": item.get("language"),
                        "updated_at": item.get("updated_at"),
                        "topics": topics,
                        "archived": bool(item.get("archived")),
                        "open_issues": item.get("open_issues_count", 0),
                        "description": description,
                        "license": (item.get("license") or {}).get("spdx_id"),
                    },
                    reliability=self.reliability,
                )
            )
        return results

    def readme_excerpt(self, full_name: str, max_chars: int = 1500) -> str:
        """Fetch a repository README when available (used for documentation QA)."""
        try:
            payload = self.http.get_json(
                f"https://api.github.com/repos/{full_name}/readme",
                ttl_hours=24,
                headers=self._headers(),
            )
        except ResearchError:
            return ""
        # The JSON endpoint returns base64 content for the README.
        content = payload.get("content") if isinstance(payload, dict) else None
        if not isinstance(content, str):
            return ""
        import base64

        try:
            decoded = base64.b64decode(content).decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            return ""
        return decoded[:max_chars]
