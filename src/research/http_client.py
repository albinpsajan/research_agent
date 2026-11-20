"""Polite HTTP client: caching, rate limiting, robots.txt and extraction."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from config.logging_config import get_logger
from config.settings import ResearchSettings, get_settings
from src.research.base import (
    PageContent,
    ResearchError,
    clean_text,
    validate_public_url,
)

logger = get_logger("research.http")

# Hosts whose documented purpose is machine access. robots.txt is aimed at
# crawlers; these endpoints are explicitly published for API clients.
_DOCUMENTED_APIS: dict[str, tuple[str, ...]] = {
    "api.github.com": ("/",),
    "export.arxiv.org": ("/api/",),
    "api.openalex.org": ("/",),
    "api.crossref.org": ("/",),
    "api.duckduckgo.com": ("/",),
    "hn.algolia.com": ("/api/",),
    "en.wikipedia.org": ("/w/api.php",),
}


def _is_documented_api(host: str, path: str) -> bool:
    prefixes = _DOCUMENTED_APIS.get(host)
    if not prefixes:
        return False
    return any(path.startswith(prefix) for prefix in prefixes)


@dataclass
class CachedResponse:
    url: str
    status_code: int
    content_type: str
    text: str
    stored_at: float


class ResearchHttpClient:
    """HTTPX wrapper used by every connector."""

    def __init__(self, settings: ResearchSettings | None = None) -> None:
        self.settings = settings or get_settings().research
        self.cache_dir = Path(get_settings().storage.cache_dir) / "http"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._client = httpx.Client(
            timeout=httpx.Timeout(self.settings.timeout_seconds, connect=10.0),
            headers={
                "User-Agent": self.settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            },
            follow_redirects=True,
            max_redirects=5,
        )

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, url: str, ttl_hours: int) -> CachedResponse | None:
        path = self._cache_path(url)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            stored_at = float(payload["stored_at"])
            if time.time() - stored_at > ttl_hours * 3600:
                return None
            return CachedResponse(**payload)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _write_cache(self, cached: CachedResponse) -> None:
        try:
            self._cache_path(cached.url).write_text(
                json.dumps(cached.__dict__, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("Could not write HTTP cache: %s", exc)

    # ------------------------------------------------------------------
    # Politeness
    # ------------------------------------------------------------------

    def _throttle(self, host: str) -> None:
        delay = self.settings.rate_limit_delay
        # arXiv's API guidance asks clients to be gentler than the default.
        if host == "export.arxiv.org":
            delay = max(delay, 3.0)
        if delay <= 0:
            return
        elapsed = time.monotonic() - self._last_request.get(host, 0.0)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request[host] = time.monotonic()

    def _robots_allowed(self, url: str) -> bool:
        if not self.settings.respect_robots_txt:
            return True
        parsed = urlparse(url)
        # Official machine APIs are designed for programmatic clients, not
        # crawlers. arXiv, for example, publishes a blanket Disallow in its
        # export host's robots.txt while explicitly documenting API use.
        if _is_documented_api(parsed.netloc.lower(), parsed.path):
            return True
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            parser = RobotFileParser()
            parser.set_url(f"{origin}/robots.txt")
            try:
                response = self._client.get(f"{origin}/robots.txt")
                if response.status_code >= 400:
                    parser = None
                else:
                    parser.parse(response.text.splitlines())
            except httpx.HTTPError:
                parser = None
            self._robots[origin] = parser
        parser = self._robots[origin]
        if parser is None:
            return True  # absent robots.txt means allowed
        try:
            return parser.can_fetch(self.settings.user_agent, url)
        except Exception:  # noqa: BLE001 - malformed robots file
            return True

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------

    def get(
        self,
        url: str,
        *,
        ttl_hours: int | None = None,
        use_cache: bool = True,
        max_bytes: int | None = None,
    ) -> CachedResponse:
        safe_url = validate_public_url(url)
        if use_cache:
            cached = self._read_cache(
                safe_url,
                ttl_hours if ttl_hours is not None else self.settings.cache_ttl_hours,
            )
            if cached:
                return cached
        host = urlparse(safe_url).netloc
        self._throttle(host)
        if not self._robots_allowed(safe_url):
            raise ResearchError(f"robots.txt disallows fetching {safe_url}")

        try:
            with self._client.stream("GET", safe_url) as response:
                if response.status_code >= 400:
                    raise ResearchError(f"HTTP {response.status_code} for {safe_url}")
                limit = max_bytes or self.settings.max_page_bytes
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > limit:
                        raise ResearchError(
                            f"Response exceeds {limit} bytes: {safe_url}"
                        )
                    chunks.append(chunk)
                content_type = response.headers.get("content-type", "")
                encoding = response.encoding or "utf-8"
                text = b"".join(chunks).decode(encoding, errors="replace")
                final_url = str(response.url)
                validate_public_url(final_url)  # redirect SSRF check
                cached = CachedResponse(
                    url=safe_url,
                    status_code=response.status_code,
                    content_type=content_type,
                    text=text,
                    stored_at=time.time(),
                )
        except httpx.HTTPError as exc:
            raise ResearchError(f"Request failed for {safe_url}: {exc}") from exc

        if use_cache:
            self._write_cache(cached)
        return cached

    def get_json(
        self,
        url: str,
        *,
        params: dict | None = None,
        ttl_hours: int = 6,
        headers: dict[str, str] | None = None,
    ) -> dict:
        """JSON GET with explicit query params (cache key includes params)."""
        if params:
            request = httpx.Request("GET", url, params=params)
            full_url = str(request.url)
        else:
            full_url = url
        safe_url = validate_public_url(full_url)
        cached = self._read_cache(safe_url, ttl_hours)
        if cached:
            try:
                return json.loads(cached.text)
            except json.JSONDecodeError:
                pass
        host = urlparse(safe_url).netloc
        self._throttle(host)
        try:
            response = self._client.get(
                safe_url, headers=headers, timeout=self.settings.timeout_seconds
            )
            response.raise_for_status()
            text = response.text
        except httpx.HTTPStatusError as exc:
            retry_after = exc.response.headers.get("retry-after")
            detail = f" (retry after {retry_after}s)" if retry_after else ""
            raise ResearchError(
                f"HTTP {exc.response.status_code} for {safe_url}{detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ResearchError(f"Request failed for {safe_url}: {exc}") from exc
        self._write_cache(
            CachedResponse(
                url=safe_url,
                status_code=200,
                content_type="application/json",
                text=text,
                stored_at=time.time(),
            )
        )
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ResearchError(f"Invalid JSON from {safe_url}") from exc
        if not isinstance(payload, dict):
            raise ResearchError(f"Unexpected JSON shape from {safe_url}")
        return payload

    # ------------------------------------------------------------------
    # Page extraction
    # ------------------------------------------------------------------

    def fetch_page(self, url: str, max_links: int = 40) -> PageContent:
        response = self.get(url, ttl_hours=self.settings.cache_ttl_hours)
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
            tag.decompose()
        title = (
            clean_text(soup.title.get_text(" ", strip=True), 300) if soup.title else ""
        )
        for tag in soup(["nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        text = clean_text(soup.get_text("\n", strip=True), 14000)
        links: list[str] = []
        base_host = urlparse(response.url).netloc
        for anchor in soup.find_all("a", href=True):
            href = urljoin(response.url, anchor["href"])
            parsed = urlparse(href)
            if parsed.scheme in ("http", "https") and parsed.netloc == base_host:
                clean = href.split("#")[0]
                if clean not in links and len(links) < max_links:
                    links.append(clean)
        try:
            soup.decompose()
        except Exception:
            pass
        return PageContent(
            url=url,
            final_url=response.url,
            title=title,
            text=text,
            links=links,
        )

    def close(self) -> None:
        self._client.close()
