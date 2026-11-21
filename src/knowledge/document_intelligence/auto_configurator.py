"""Automatic HackathonIQ Configuration Engine from Document Intelligence."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from config.logging_config import get_logger
from src.knowledge.document_intelligence.consolidator import DocumentConsolidator
from src.knowledge.document_intelligence.models import (
    DocumentType,
    ExtractedConflict,
    MissingInfoStatus,
    StructuredHackathonDoc,
    UploadedDocument,
)
from src.models.hackathon import (
    HackathonInput,
    HackathonTrack,
    MultiTrackMode,
)

logger = get_logger("knowledge.document_intelligence.auto_configurator")


class HackathonAutoConfigurator:
    """Transforms consolidated document understanding into a ready-to-execute HackathonInput."""

    @classmethod
    def configure_hackathon(
        cls,
        profile: StructuredHackathonDoc,
        documents: list[UploadedDocument],
        multi_track_mode: MultiTrackMode = MultiTrackMode.BEST_OVERALL,
        user_overrides: dict[str, Any] | None = None,
    ) -> tuple[HackathonInput | None, MissingInfoStatus, list[ExtractedConflict]]:
        """Automatically builds HackathonInput configuration from extracted document profile."""
        user_overrides = user_overrides or {}

        # Check if any documents exist
        primary_doc = documents[0] if documents else None
        primary_filename = primary_doc.filename if primary_doc else "Uploaded_Document.pdf"
        is_hackathon_type = any(
            d.document_type in (DocumentType.OFFICIAL_RULES, DocumentType.EVENT_ANNOUNCEMENT, DocumentType.TRACK_DESCRIPTION)
            for d in documents
        ) if documents else True

        # Audit missing information
        status = DocumentConsolidator.audit_missing_information(profile, is_hackathon_doc=is_hackathon_type)

        # Handle essential fields: Theme
        theme = user_overrides.get("theme") or profile.theme
        if not theme or len(theme.strip()) < 3:
            # If tracks are available, synthesize a theme from track names
            if profile.tracks or profile.extracted_tracks:
                track_names = [t.name for t in profile.extracted_tracks] or profile.tracks
                theme = f"Multi-Track Innovation: {', '.join(track_names[:3])}"
            elif not is_hackathon_type and profile.problem_statements:
                theme = f"Evidence-Driven Research: {profile.problem_statements[0][:120]}"
            elif primary_doc:
                clean_name = primary_filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
                theme = f"Domain Research Challenge: {clean_name}"

        # If still no theme, cannot proceed
        if not theme or len(theme.strip()) < 3:
            status.is_ready_for_research = False
            status.missing_essential = ["theme"]
            status.suggested_action = "Please provide a hackathon theme or challenge topic to initiate research."
            return None, status, profile.conflicts

        # Hackathon Name
        name = user_overrides.get("name") or profile.hackathon_name
        if not name:
            if primary_doc:
                name = primary_filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
            else:
                name = "Autonomous Document-Driven Research Session"

        # Official Website
        website = user_overrides.get("website_url") or profile.official_website
        if website and not website.startswith(("http://", "https://")):
            website = f"https://{website}"

        # Rules URL: Use official URL or link to primary uploaded doc
        rules_url = user_overrides.get("rules_url") or (f"doc://{primary_filename}" if primary_filename else None)

        # Parse deadline safely
        deadline = cls._parse_deadline(user_overrides.get("deadline") or profile.submission_deadline)

        # Dynamic tracks
        extracted_tracks = profile.extracted_tracks
        tracks: list[HackathonTrack] = []
        if extracted_tracks:
            for t in extracted_tracks:
                tracks.append(
                    HackathonTrack(
                        name=t.name,
                        description=t.description or "",
                        track_rules=t.track_rules or "",
                        official_track_url="",
                    )
                )
        elif profile.tracks:
            for t_name in profile.tracks:
                tracks.append(
                    HackathonTrack(
                        name=t_name,
                        description="",
                        track_rules="",
                        official_track_url="",
                    )
                )

        is_multi_track = len(tracks) >= 2

        # Build combined constraints from document facts
        constraints_list: list[str] = []
        if profile.event_duration:
            constraints_list.append(f"Event Duration: {profile.event_duration}")
        if profile.technical_restrictions:
            constraints_list.append(f"Technical Rules: {'; '.join(profile.technical_restrictions[:4])}")
        if profile.required_technologies:
            constraints_list.append(f"Required Technologies: {', '.join(profile.required_technologies[:4])}")
        if profile.geographic_restrictions:
            constraints_list.append(f"Geographic Scope: {', '.join(profile.geographic_restrictions[:3])}")
        if profile.sponsor_requirements:
            constraints_list.append(f"Sponsor Directives: {'; '.join(profile.sponsor_requirements[:3])}")
        if profile.submission_requirements:
            constraints_list.append(f"Deliverables: {'; '.join(profile.submission_requirements[:3])}")

        if user_overrides.get("constraints"):
            constraints_list.append(user_overrides["constraints"])

        combined_constraints = " | ".join(constraints_list) if constraints_list else None

        hackathon_input = HackathonInput(
            theme=theme.strip(),
            name=name.strip(),
            website_url=website.strip() if website else None,
            rules_url=rules_url,
            deadline=deadline,
            constraints=combined_constraints,
            is_multi_track=is_multi_track,
            multi_track_mode=multi_track_mode if is_multi_track else MultiTrackMode.BEST_OVERALL,
            tracks=tracks if is_multi_track else [],
        )

        status.is_ready_for_research = True
        return hackathon_input, status, profile.conflicts

    @staticmethod
    def _parse_deadline(val: str | None) -> date | None:
        """Parse diverse date formats safely without hallucinating."""
        if not val or not isinstance(val, str):
            return None

        # Clean string
        val_clean = val.strip()

        # Try ISO format YYYY-MM-DD
        iso_match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", val_clean)
        if iso_match:
            try:
                y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
                return date(y, m, d)
            except ValueError:
                pass

        # Try DD/MM/YYYY or MM/DD/YYYY
        slash_match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", val_clean)
        if slash_match:
            try:
                d, m, y = int(slash_match.group(1)), int(slash_match.group(2)), int(slash_match.group(3))
                return date(y, m, d)
            except ValueError:
                pass

        # Try Month DD, YYYY
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"):
            try:
                dt = datetime.strptime(val_clean, fmt)
                return dt.date()
            except ValueError:
                continue

        return None
