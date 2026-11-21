"""Ingestion subsystem for the Hackathon Playbook Knowledge Base.

Provides structured ingestion with full origin and provenance tracking for:
- YouTube Hackathon Judge & Winner Retrospectives (metadata via oEmbed, transcript probe)
- Public Articles & Playbooks (Devpost, MLH, Medium, Substack)
- Winning Open-Source Repositories (GitHub README inspection, winner badges)
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any
from uuid import uuid4

from config.logging_config import get_logger
from src.knowledge.hackathon_playbook.schema import (
    PlaybookCategory,
    PlaybookEntry,
    PlaybookProvenanceType,
)

logger = get_logger("knowledge.hackathon_playbook.ingestion")

DEFAULT_TIMEOUT = 8


class YouTubePlaybookIngester:
    """Ingests lessons learned from YouTube hackathon retrospectives and judge panels."""

    OEMBED_BASE = "https://www.youtube.com/oembed"

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    @staticmethod
    def extract_video_id(url: str) -> str | None:
        """Extract YouTube 11-char video ID from various standard URL formats."""
        patterns = [
            r"youtube\.com/watch\?.*v=([0-9A-Za-z_-]{11})",
            r"youtu\.be/([0-9A-Za-z_-]{11})",
            r"youtube\.com/embed/([0-9A-Za-z_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def fetch_oembed_metadata(self, url: str) -> dict[str, Any]:
        """Fetch official video metadata (title, author, provider) via YouTube oEmbed API."""
        encoded_url = urllib.parse.quote(url, safe="")
        oembed_url = f"{self.OEMBED_BASE}?url={encoded_url}&format=json"
        try:
            req = urllib.request.Request(oembed_url, headers={"User-Agent": "HackathonIQ/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "title": data.get("title", ""),
                    "author_name": data.get("author_name", ""),
                    "author_url": data.get("author_url", ""),
                    "provider_name": data.get("provider_name", "YouTube"),
                    "status": "success",
                }
        except Exception as e:
            logger.warning(f"Failed to fetch YouTube oEmbed for {url}: {e}")
            return {
                "title": "",
                "author_name": "",
                "author_url": "",
                "provider_name": "YouTube",
                "status": f"failed: {e}",
            }

    def check_transcript_availability(self, url: str) -> dict[str, Any]:
        """Inspect video page to determine whether closed captions/transcripts genuinely exist.

        If transcripts are not available or disabled, record transcript_available=False
        and transcript_status='unavailable_or_disabled' without fabricating content.
        """
        video_id = self.extract_video_id(url)
        if not video_id:
            return {
                "transcript_available": False,
                "transcript_status": "invalid_youtube_url",
                "caption_tracks_found": False,
            }

        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            req = urllib.request.Request(
                watch_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                caption_present = "captionTracks" in html
                return {
                    "transcript_available": caption_present,
                    "transcript_status": "available" if caption_present else "unavailable_or_disabled",
                    "caption_tracks_found": caption_present,
                    "video_id": video_id,
                }
        except Exception as e:
            logger.warning(f"Could not probe YouTube transcript for {video_id}: {e}")
            return {
                "transcript_available": False,
                "transcript_status": f"probe_error: {e}",
                "caption_tracks_found": False,
                "video_id": video_id,
            }

    def ingest_retrospective(
        self,
        url: str,
        lesson_title: str,
        lesson: str,
        actionable_guidance: str,
        target_agent: str,
        category: PlaybookCategory = PlaybookCategory.WINNER_PATTERNS,
        kerala_india_applicability: str = "",
        tags: list[str] | None = None,
        confidence: float = 0.95,
        entry_id: str | None = None,
    ) -> PlaybookEntry:
        """Ingest a YouTube retrospective lesson with full provenance metadata."""
        meta = self.fetch_oembed_metadata(url)
        transcript_info = self.check_transcript_availability(url)

        author = meta.get("author_name") or "YouTube Hackathon Creator"
        title = lesson_title or meta.get("title") or "Hackathon Retrospective Lesson"

        return PlaybookEntry(
            id=entry_id or f"HP-YT-{uuid4().hex[:6]}",
            category=category,
            title=title,
            source_origin="youtube_retrospective",
            lesson=lesson,
            actionable_guidance=actionable_guidance,
            target_agent=target_agent,
            kerala_india_applicability=kerala_india_applicability,
            tags=tags or ["youtube", "retrospective", "provenance"],
            confidence=confidence,
            provenance_type=PlaybookProvenanceType.JUDGE_RETROSPECTIVE.value,
            source_url=url,
            author_or_creator=author,
            publication_date="2024",
            transcript_available=transcript_info["transcript_available"],
            readme_reference="",
        )


class WebsitePlaybookIngester:
    """Ingests lessons learned from public hackathon guides, judging rubrics, and engineering blogs."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    def fetch_article_metadata(self, url: str) -> dict[str, Any]:
        """Fetch article HTML and extract title, author, and published date."""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HackathonIQ/1.0"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

                title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
                title = title_match.group(1).strip() if title_match else ""

                author_match = re.search(r'<meta\s+name=["\']author["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                author = author_match.group(1).strip() if author_match else ""

                date_match = re.search(r'<meta\s+(?:property|name)=["\'](?:article:published_time|date)["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                date = date_match.group(1).strip() if date_match else ""

                return {
                    "title": title,
                    "author": author,
                    "published_date": date,
                    "status": "success",
                }
        except Exception as e:
            logger.warning(f"Failed to fetch article metadata for {url}: {e}")
            return {
                "title": "",
                "author": "",
                "published_date": "",
                "status": f"failed: {e}",
            }

    def ingest_guide(
        self,
        url: str,
        lesson_title: str,
        lesson: str,
        actionable_guidance: str,
        target_agent: str,
        category: PlaybookCategory,
        provenance_type: PlaybookProvenanceType = PlaybookProvenanceType.PARTICIPANT_GUIDE,
        source_origin: str = "web_guide",
        author: str = "",
        kerala_india_applicability: str = "",
        tags: list[str] | None = None,
        confidence: float = 0.95,
        entry_id: str | None = None,
    ) -> PlaybookEntry:
        """Ingest a web guide or official judging rubric entry with provenance."""
        meta = self.fetch_article_metadata(url)
        author_resolved = author or meta.get("author") or "Hackathon Practitioner"
        date_resolved = meta.get("published_date") or "2024"

        return PlaybookEntry(
            id=entry_id or f"HP-WEB-{uuid4().hex[:6]}",
            category=category,
            title=lesson_title or meta.get("title") or "Hackathon Guidance",
            source_origin=source_origin,
            lesson=lesson,
            actionable_guidance=actionable_guidance,
            target_agent=target_agent,
            kerala_india_applicability=kerala_india_applicability,
            tags=tags or ["guide", "playbook", "provenance"],
            confidence=confidence,
            provenance_type=provenance_type.value,
            source_url=url,
            author_or_creator=author_resolved,
            publication_date=date_resolved,
            transcript_available=False,
            readme_reference="",
        )


class GitHubPlaybookIngester:
    """Ingests winning patterns and architectural lessons from real winning GitHub hackathon repositories."""

    RAW_GITHUB_BASE = "https://raw.githubusercontent.com"

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    @staticmethod
    def parse_repo_slug(url_or_slug: str) -> tuple[str, str]:
        """Extract (owner, repo) from GitHub URL or slug."""
        clean = url_or_slug.strip().rstrip("/")
        match = re.search(r"github\.com/([^/]+)/([^/]+)", clean)
        if match:
            return match.group(1), match.group(2)
        parts = clean.split("/")
        if len(parts) == 2:
            return parts[0], parts[1]
        raise ValueError(f"Invalid GitHub repository URL or slug: {url_or_slug}")

    def fetch_readme(self, owner: str, repo: str) -> str:
        """Fetch raw README.md from HEAD branch."""
        url = f"{self.RAW_GITHUB_BASE}/{owner}/{repo}/HEAD/README.md"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HackathonIQ/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Could not fetch README for {owner}/{repo}: {e}")
            return ""

    def analyze_winner_repository(self, repo_url_or_slug: str) -> dict[str, Any]:
        """Inspect repository README for winner badges, devpost links, and architectural lessons."""
        try:
            owner, repo = self.parse_repo_slug(repo_url_or_slug)
        except ValueError as e:
            return {"status": "error", "message": str(e)}

        readme = self.fetch_readme(owner, repo)
        if not readme:
            return {
                "owner": owner,
                "repo": repo,
                "status": "readme_not_found",
                "is_winner_verified": False,
                "detected_accolades": [],
            }

        # Scan for winner indicators
        winner_keywords = [
            r"(?i)\b1st\s+place\b",
            r"(?i)\bfirst\s+place\b",
            r"(?i)\bgrand\s+prize\b",
            r"(?i)\bhackathon\s+winner\b",
            r"(?i)\bdevpost\.com/software\b",
            r"(?i)\bbest\s+use\s+of\b",
            r"(?i)\boverall\s+winner\b",
        ]
        accolades = []
        for kw in winner_keywords:
            matches = re.findall(kw, readme)
            if matches:
                accolades.extend(matches)

        # Extract offline / local AI / architecture snippets
        has_offline = bool(re.search(r"(?i)\b(offline|local\s+llm|ollama|sqlite|edge)\b", readme))
        has_architecture = bool(re.search(r"(?i)\b(architecture|data\s+flow|pipeline|diagram)\b", readme))

        return {
            "owner": owner,
            "repo": repo,
            "status": "success",
            "is_winner_verified": len(accolades) > 0,
            "detected_accolades": list(set(accolades)),
            "features_offline": has_offline,
            "has_architecture_section": has_architecture,
            "readme_snippet": readme[:500],
        }

    def ingest_winner_repo(
        self,
        repo_url: str,
        lesson_title: str,
        lesson: str,
        actionable_guidance: str,
        target_agent: str,
        category: PlaybookCategory = PlaybookCategory.WINNER_PATTERNS,
        kerala_india_applicability: str = "",
        tags: list[str] | None = None,
        confidence: float = 0.95,
        entry_id: str | None = None,
    ) -> PlaybookEntry:
        """Ingest a verified winning repository as an actionable playbook entry."""
        owner, repo = self.parse_repo_slug(repo_url)
        analysis = self.analyze_winner_repository(f"{owner}/{repo}")

        author = owner
        resolved_tags = tags or ["github", "winning_repo", "open_source"]
        if analysis.get("is_winner_verified"):
            resolved_tags.append("verified_winner")

        return PlaybookEntry(
            id=entry_id or f"HP-GH-{uuid4().hex[:6]}",
            category=category,
            title=lesson_title,
            source_origin=f"github_{owner}_{repo}",
            lesson=lesson,
            actionable_guidance=actionable_guidance,
            target_agent=target_agent,
            kerala_india_applicability=kerala_india_applicability,
            tags=resolved_tags,
            confidence=confidence,
            provenance_type=PlaybookProvenanceType.ENGINEERING_LESSON.value,
            source_url=f"https://github.com/{owner}/{repo}",
            author_or_creator=author,
            publication_date="2024",
            transcript_available=False,
            readme_reference=analysis.get("readme_snippet", "")[:200],
        )
