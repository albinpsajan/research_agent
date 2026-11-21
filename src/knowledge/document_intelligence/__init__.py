"""Document Intelligence package for HackathonIQ."""

from src.knowledge.document_intelligence.auto_configurator import (
    HackathonAutoConfigurator,
)
from src.knowledge.document_intelligence.classifier import DocumentClassifier
from src.knowledge.document_intelligence.consolidator import DocumentConsolidator
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
    ExtractedConflict,
    ExtractedTrack,
    ExtractionMethod,
    ExtractionStatus,
    MissingInfoStatus,
    ProvenancedField,
    ProvenancedItem,
    StructuredHackathonDoc,
    StructuredResearchDoc,
    UploadedDocument,
)
from src.knowledge.document_intelligence.service import DocumentIntelligenceService

__all__ = [
    "DocumentChunk",
    "DocumentClassifier",
    "DocumentConsolidator",
    "DocumentExtractor",
    "DocumentIntelligenceService",
    "DocumentPage",
    "DocumentSearchHit",
    "DocumentType",
    "ExtractedConflict",
    "ExtractedTrack",
    "ExtractionError",
    "ExtractionMethod",
    "ExtractionStatus",
    "HackathonAutoConfigurator",
    "MissingInfoStatus",
    "OCREngine",
    "ProvenancedField",
    "ProvenancedItem",
    "StructuredHackathonDoc",
    "StructuredResearchDoc",
    "UploadedDocument",
    "sanitize_filename",
    "sanitize_for_prompt_injection",
    "validate_uploaded_file",
]
