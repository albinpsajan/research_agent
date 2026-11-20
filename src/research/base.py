"""Shared research types and validation helpers."""

from __future__ import annotations

import ipaddress
import re
import socket
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from src.utils.hackathon_time import utc_now


class ResearchError(RuntimeError):
    """A connector or page fetch failed in a recoverable way."""


class SearchResult(BaseModel):
    """A real, retrievable research hit with provenance."""

    title: str
    url: str
    snippet: str = ""
    source_type: str = "web"
    published_at: Optional[datetime] = None
    authors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    reliability: float = Field(default=0.5, ge=0, le=1)

    def as_context(self, index: int) -> str:
        date = (
            self.published_at.strftime("%Y-%m-%d")
            if self.published_at
            else "undated"
        )
        meta = ""
        if self.metadata.get("stars") is not None:
            meta = (
                f" | stars={self.metadata.get('stars')}"
                f" | updated={self.metadata.get('updated_at', '?')}"
            )
        return (
            f"[S{index}] ({self.source_type}, {date}) {self.title}\n"
            f"URL: {self.url}\n{self.snippet[:700]}{meta}"
        )


class PageContent(BaseModel):
    """Extracted readable page content."""

    url: str
    final_url: str
    title: str
    text: str
    links: list[str] = Field(default_factory=list)
    retrieved_at: datetime = Field(default_factory=utc_now)


_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
}


def validate_public_url(url: str) -> str:
    """Reject non-HTTP(S), credentialed and private-network URLs (SSRF guard)."""
    candidate = (url or "").strip()
    if not candidate:
        raise ResearchError("Empty URL")
    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https"):
        raise ResearchError(f"Unsupported URL scheme: {parsed.scheme or 'none'}")
    if parsed.username or parsed.password:
        raise ResearchError("URLs with embedded credentials are not allowed")
    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTS or host.endswith(".local"):
        raise ResearchError(f"Blocked host: {host or 'missing'}")
    try:
        ip = ipaddress.ip_address(host)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise ResearchError(f"Private or reserved address blocked: {host}")
    except ValueError:
        # Hostname: resolve and check every address to prevent DNS rebinding.
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror as exc:
            raise ResearchError(f"Cannot resolve host {host}") from exc
        for info in infos:
            address = info[4][0]
            try:
                ip = ipaddress.ip_address(address)
            except ValueError:
                continue
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
            ):
                raise ResearchError(
                    f"Host {host} resolves to a private address"
                )
    return candidate


def clean_text(text: str, limit: int = 12000) -> str:
    """Collapse whitespace and bound length."""
    collapsed = re.sub(r"[ \t\r\f\v]+", " ", text or "")
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed).strip()
    return collapsed[:limit]


def query_terms(query: str, limit: int = 6) -> list[str]:
    """Extract meaningful lowercase terms for simple relevance filtering."""
    stop = {
        "the", "and", "for", "with", "from", "that", "this", "into", "using",
        "based", "system", "systems", "data", "new", "how", "why", "what",
    }
    terms = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", query.lower())
    seen: list[str] = []
    for term in terms:
        if term not in stop and term not in seen:
            seen.append(term)
    return seen[:limit]
