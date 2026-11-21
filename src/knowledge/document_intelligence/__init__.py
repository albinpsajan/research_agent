"""Document Intelligence package for HackathonIQ."""

from src.knowledge.document_intelligence.extractor import (
    DocumentExtractor,
    ExtractionError,
    OCREngine,
    sanitize_filename,
    sanitize_for_prompt_injection,
    validate_uploaded_file,
)
from src.knowledge.document_intelligence.models import (
    DocumentChunk,
    DocumentPage,
    DocumentSearchHit,
    DocumentType,
    ExtractionMethod,
    ExtractionStatus,
    StructuredHackathonDoc,
    StructuredResearchDoc,
    UploadedDocument,
)
from src.knowledge.document_intelligence.service import DocumentIntelligenceService

__all__ = [
    "DocumentChunk",
    "DocumentExtractor",
    "DocumentIntelligenceService",
    "DocumentPage",
    "DocumentSearchHit",
    "DocumentType",
    "ExtractionError",
    "ExtractionMethod",
    "ExtractionStatus",
    "OCREngine",
    "StructuredHackathonDoc",
    "StructuredResearchDoc",
    "UploadedDocument",
    "sanitize_filename",
    "sanitize_for_prompt_injection",
    "validate_uploaded_file",
]
