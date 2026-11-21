"""Consolidator for multiple uploaded documents, section relationships and conflict detection."""

from __future__ import annotations

from config.logging_config import get_logger
from src.knowledge.document_intelligence.models import (
    DocumentType,
    ExtractedConflict,
    ExtractedTrack,
    MissingInfoStatus,
    ProvenancedField,
    ProvenancedItem,
    StructuredHackathonDoc,
)

logger = get_logger("knowledge.document_intelligence.consolidator")


class DocumentConsolidator:
    """Merges structured intelligence across multiple documents and detects conflicting facts."""

    @staticmethod
    def consolidate_hackathon_profiles(
        profiles: list[tuple[StructuredHackathonDoc, str, DocumentType]],
    ) -> tuple[StructuredHackathonDoc, list[ExtractedConflict]]:
        """Consolidate multiple hackathon profiles into one unified profile with conflict detection.

        Args:
            profiles: List of tuples (profile, source_filename, document_type).
        """
        if not profiles:
            return StructuredHackathonDoc(), []

        # Sort so official rules have highest priority for authoritative fields
        priority_order = {
            DocumentType.OFFICIAL_RULES: 0,
            DocumentType.TRACK_DESCRIPTION: 1,
            DocumentType.EVENT_ANNOUNCEMENT: 2,
            DocumentType.TECHNICAL_SPEC: 3,
            DocumentType.GENERAL_EVIDENCE: 4,
            DocumentType.SUPPORTING_MATERIAL: 5,
        }
        sorted_profiles = sorted(
            profiles,
            key=lambda item: priority_order.get(item[2], 99),
        )

        consolidated = StructuredHackathonDoc()
        conflicts: list[ExtractedConflict] = []

        seen_tracks: dict[str, ExtractedTrack] = {}
        seen_deadlines: dict[str, str] = {}  # source -> deadline
        seen_durations: dict[str, str] = {}  # source -> duration

        for prof, fname, dtype in sorted_profiles:
            # 1. Hackathon Name
            if prof.hackathon_name and not consolidated.hackathon_name:
                consolidated.hackathon_name = prof.hackathon_name
                consolidated.provenanced_fields["hackathon_name"] = prof.get_field_provenance("hackathon_name") or ProvenancedField(
                    value=prof.hackathon_name,
                    filename=fname,
                    page=1,
                    confidence=0.95 if dtype == DocumentType.OFFICIAL_RULES else 0.85,
                    is_inferred=False,
                )
            elif (
                prof.hackathon_name
                and consolidated.hackathon_name
                and prof.hackathon_name.strip().lower() != consolidated.hackathon_name.strip().lower()
            ):
                conflicts.append(
                    ExtractedConflict(
                        field="hackathon_name",
                        item_a=consolidated.hackathon_name,
                        source_a=consolidated.provenanced_fields["hackathon_name"].filename,
                        item_b=prof.hackathon_name,
                        source_b=fname,
                        explanation=f"Conflicting event name across documents: '{consolidated.hackathon_name}' vs '{prof.hackathon_name}'",
                    )
                )

            # 2. Organizer
            if prof.organizer and not consolidated.organizer:
                consolidated.organizer = prof.organizer
                consolidated.provenanced_fields["organizer"] = prof.get_field_provenance("organizer") or ProvenancedField(
                    value=prof.organizer,
                    filename=fname,
                    page=1,
                    confidence=0.90,
                    is_inferred=False,
                )

            # 3. Official Website
            if prof.official_website and not consolidated.official_website:
                consolidated.official_website = prof.official_website
                consolidated.provenanced_fields["official_website"] = prof.get_field_provenance("official_website") or ProvenancedField(
                    value=prof.official_website,
                    filename=fname,
                    page=1,
                    confidence=0.95,
                    is_inferred=False,
                )

            # 4. Theme
            if prof.theme and not consolidated.theme:
                consolidated.theme = prof.theme
                consolidated.provenanced_fields["theme"] = prof.get_field_provenance("theme") or ProvenancedField(
                    value=prof.theme,
                    filename=fname,
                    page=1,
                    confidence=0.90,
                    is_inferred=False,
                )

            # 5. Tracks
            # Gather tracks from both prof.extracted_tracks and prof.tracks
            for t_obj in prof.extracted_tracks:
                norm_key = t_obj.name.strip().lower()
                if norm_key not in seen_tracks:
                    seen_tracks[norm_key] = t_obj
                else:
                    # Enrich description if empty
                    existing = seen_tracks[norm_key]
                    if not existing.description and t_obj.description:
                        existing.description = t_obj.description

            for raw_t in prof.tracks:
                norm_key = raw_t.strip().lower()
                if norm_key not in seen_tracks:
                    seen_tracks[norm_key] = ExtractedTrack(
                        name=raw_t.strip(),
                        source_filename=fname,
                        source_page=1,
                        confidence=0.90,
                    )

            # 6. Deadlines & Dates
            deadline_val = prof.submission_deadline or (prof.important_deadlines[0] if prof.important_deadlines else None)
            if deadline_val:
                seen_deadlines[fname] = deadline_val
                if not consolidated.submission_deadline:
                    consolidated.submission_deadline = deadline_val
                    consolidated.provenanced_fields["submission_deadline"] = prof.get_field_provenance("submission_deadline") or ProvenancedField(
                        value=deadline_val,
                        filename=fname,
                        page=1,
                        confidence=0.90,
                        is_inferred=False,
                    )

            # Check deadline conflicts
            if len(seen_deadlines) > 1:
                vals = list(seen_deadlines.values())
                fnames = list(seen_deadlines.keys())
                if vals[0].strip().lower() != vals[1].strip().lower() and not any(c.field == "submission_deadline" for c in conflicts):
                    conflicts.append(
                        ExtractedConflict(
                            field="submission_deadline",
                            item_a=vals[0],
                            source_a=fnames[0],
                            item_b=vals[1],
                            source_b=fnames[1],
                            explanation=f"Conflicting deadlines recorded across documents: '{vals[0]}' in {fnames[0]} vs '{vals[1]}' in {fnames[1]}",
                        )
                    )

            # 7. Duration
            if prof.event_duration:
                seen_durations[fname] = prof.event_duration
                if not consolidated.event_duration:
                    consolidated.event_duration = prof.event_duration
                    consolidated.provenanced_fields["event_duration"] = prof.get_field_provenance("event_duration") or ProvenancedField(
                        value=prof.event_duration,
                        filename=fname,
                        page=1,
                        confidence=0.90,
                        is_inferred=False,
                    )

            # 8. List Items: Rules, Criteria, Constraints, Tech
            _merge_provenanced_items(
                consolidated=consolidated,
                incoming=prof,
                category="judging_criteria",
                string_list_attr="judging_criteria",
                default_filename=fname,
            )
            _merge_provenanced_items(
                consolidated=consolidated,
                incoming=prof,
                category="technical_restrictions",
                string_list_attr="technical_restrictions",
                default_filename=fname,
            )
            _merge_provenanced_items(
                consolidated=consolidated,
                incoming=prof,
                category="eligibility_requirements",
                string_list_attr="eligibility_requirements",
                default_filename=fname,
            )
            _merge_provenanced_items(
                consolidated=consolidated,
                incoming=prof,
                category="geographic_restrictions",
                string_list_attr="geographic_restrictions",
                default_filename=fname,
            )
            _merge_provenanced_items(
                consolidated=consolidated,
                incoming=prof,
                category="required_technologies",
                string_list_attr="required_technologies",
                default_filename=fname,
            )
            _merge_provenanced_items(
                consolidated=consolidated,
                incoming=prof,
                category="sponsor_requirements",
                string_list_attr="sponsor_requirements",
                default_filename=fname,
            )
            _merge_provenanced_items(
                consolidated=consolidated,
                incoming=prof,
                category="submission_requirements",
                string_list_attr="submission_requirements",
                default_filename=fname,
            )
            _merge_provenanced_items(
                consolidated=consolidated,
                incoming=prof,
                category="problem_statements",
                string_list_attr="problem_statements",
                default_filename=fname,
            )

            # Append facts and inferences
            consolidated.extracted_facts.extend([f"[{fname}] {fact}" for fact in prof.extracted_facts if fact not in consolidated.extracted_facts])
            consolidated.inferences.extend([f"[{fname}] {inf}" for inf in prof.inferences if inf not in consolidated.inferences])
            consolidated.unverified_items.extend([f"[{fname}] {unv}" for unv in prof.unverified_items if unv not in consolidated.unverified_items])

        # Assign consolidated tracks
        consolidated.extracted_tracks = list(seen_tracks.values())
        consolidated.tracks = [t.name for t in consolidated.extracted_tracks]
        consolidated.conflicts = conflicts

        return consolidated, conflicts

    @staticmethod
    def audit_missing_information(
        profile: StructuredHackathonDoc,
        is_hackathon_doc: bool = True,
    ) -> MissingInfoStatus:
        """Evaluate if sufficient information is available to initiate automated research."""
        missing_essential: list[str] = []
        missing_optional: list[str] = []

        if not is_hackathon_doc:
            return MissingInfoStatus(
                is_ready_for_research=True,
                is_hackathon_event=False,
                suggested_action="Document is scientific or civic research evidence. Configured problem discovery session.",
            )

        # Essential check: theme or at least 1 track
        has_theme = bool(profile.theme and len(profile.theme.strip()) >= 3)
        has_tracks = bool(profile.tracks or profile.extracted_tracks)

        if not has_theme and not has_tracks:
            missing_essential.append("theme")

        # Optional check: name, deadline, organizer, rules
        if not profile.hackathon_name:
            missing_optional.append("hackathon_name")
        if not profile.submission_deadline and not profile.important_deadlines:
            missing_optional.append("submission_deadline")
        if not profile.organizer:
            missing_optional.append("organizer")
        if not profile.judging_criteria:
            missing_optional.append("judging_criteria")

        is_ready = len(missing_essential) == 0

        action = (
            "Ready for automatic research execution."
            if is_ready
            else f"Please supply essential field: {', '.join(missing_essential)} before proceeding."
        )

        return MissingInfoStatus(
            is_ready_for_research=is_ready,
            is_hackathon_event=True,
            missing_essential=missing_essential,
            missing_optional=missing_optional,
            suggested_action=action,
        )


def _merge_provenanced_items(
    consolidated: StructuredHackathonDoc,
    incoming: StructuredHackathonDoc,
    category: str,
    string_list_attr: str,
    default_filename: str,
) -> None:
    """Helper to merge provenanced items and string lists idempotently."""
    current_items = consolidated.provenanced_items.setdefault(category, [])
    current_strings = getattr(consolidated, string_list_attr)

    incoming_prov = incoming.provenanced_items.get(category, [])
    for p_item in incoming_prov:
        if not any(item.text.strip().lower() == p_item.text.strip().lower() for item in current_items):
            current_items.append(p_item)
            if p_item.text not in current_strings:
                current_strings.append(p_item.text)

    # Also check string list
    incoming_strings = getattr(incoming, string_list_attr, [])
    for s_item in incoming_strings:
        if not any(item.text.strip().lower() == s_item.strip().lower() for item in current_items):
            p = ProvenancedItem(
                text=s_item,
                filename=default_filename,
                page=1,
                confidence=0.85,
                is_inferred=False,
            )
            current_items.append(p)
            if s_item not in current_strings:
                current_strings.append(s_item)
