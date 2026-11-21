"""Automatic Document Classifier for Document Intelligence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from config.logging_config import get_logger
from src.knowledge.document_intelligence.models import DocumentType

if TYPE_CHECKING:
    from src.llm.client import LLMClientProtocol

logger = get_logger("knowledge.document_intelligence.classifier")


class DocumentClassifier:
    """Classifies uploaded documents into semantic document types."""

    def __init__(self, llm: LLMClientProtocol | None = None) -> None:
        self.llm = llm

    def classify_document(
        self,
        filename: str,
        full_text: str,
        headings: list[str] | None = None,
    ) -> tuple[DocumentType, float]:
        """Determine document type from filename, content and structural headings."""
        text_lower = full_text[:4000].lower()
        filename_lower = filename.lower()
        headings_lower = [h.lower() for h in (headings or [])]
        combined_text = f"{filename_lower}\n{' '.join(headings_lower)}\n{text_lower}"

        # 1. Official Hackathon Rules & Guidelines
        rule_indicators = [
            "official rules", "hackathon guidelines", "rulebook", "judging criteria",
            "evaluation criteria", "eligibility criteria", "terms and conditions",
            "code of conduct", "submission rules", "hackathon rulebook",
        ]
        if any(ind in combined_text for ind in rule_indicators):
            return DocumentType.OFFICIAL_RULES, 0.95

        # 2. Track Descriptions / Problem Briefs
        track_indicators = [
            "track description", "problem statement", "challenge track",
            "theme and tracks", "sub-theme", "tracks:", "challenge areas",
        ]
        if any(ind in combined_text for ind in track_indicators) and ("hackathon" in combined_text or "challenge" in combined_text):
            return DocumentType.TRACK_DESCRIPTION, 0.90

        # 3. Event Announcement / Kickoff Poster
        announcement_indicators = [
            "announcing", "inviting applications", "call for participation",
            "registration open", "cash prizes", "hackathon poster", "save the date",
            "kickoff", "symposium announcement",
        ]
        if any(ind in combined_text for ind in announcement_indicators) and ("hackathon" in combined_text or "code fest" in combined_text):
            return DocumentType.EVENT_ANNOUNCEMENT, 0.88

        # 4. Academic Research Paper / Scientific Study
        academic_indicators = [
            "abstract", "introduction", "methodology", "literature review",
            "arxiv", "ieee", "doi:", "references\n", "experimental results",
            "journal of", "proceedings of",
        ]
        academic_matches = sum(1 for ind in academic_indicators if ind in text_lower)
        if academic_matches >= 3 or ("abstract" in text_lower and "references" in text_lower):
            return DocumentType.RESEARCH_PAPER, 0.92

        # 5. Government / Policy / Survey Report
        gov_indicators = [
            "government of", "ministry of", "department of", "gazette",
            "kerala state", "policy brief", "survey report", "niti aayog",
            "district administration", "annual report", "census of india",
        ]
        if any(ind in combined_text for ind in gov_indicators):
            return DocumentType.GOVERNMENT_REPORT, 0.90

        # 6. Dataset Documentation / Data Dictionary
        dataset_indicators = [
            "dataset description", "data dictionary", "schema definition",
            "column name", "metadata documentation", "attributes:", "data collection methodology",
        ]
        if any(ind in combined_text for ind in dataset_indicators):
            return DocumentType.DATASET_DOCUMENTATION, 0.88

        # 7. Fallback Hackathon check
        if "hackathon" in combined_text or "ideathon" in combined_text or "datathon" in combined_text:
            return DocumentType.OFFICIAL_RULES, 0.75

        # 8. General Evidence Fallback
        return DocumentType.GENERAL_EVIDENCE, 0.60
