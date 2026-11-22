"""Pydantic data models for Document Intelligence, text extraction and evidence provenance."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.utils.hackathon_time import utc_now


class DocumentType(StrEnum):
    """Categorization of uploaded documents."""

    OFFICIAL_RULES = "official_rules"              # Hackathon rulebook, official challenge guidelines
    EVENT_ANNOUNCEMENT = "event_announcement"      # Event posters, brochures, kick-off notices
    TRACK_DESCRIPTION = "track_description"        # Dedicated problem/track briefs
    RESEARCH_PAPER = "research_paper"              # Academic papers, scientific studies, whitepapers
    GOVERNMENT_REPORT = "government_report"        # Policy briefs, state surveys, gazettes
    DATASET_DOCUMENTATION = "dataset_documentation"# Dataset dictionaries, data schema specs
    SUPPORTING_MATERIAL = "supporting_material"    # General articles, slide decks, supplemental
    TECHNICAL_SPEC = "technical_spec"              # Architecture docs, API specs, developer guides
    GENERAL_EVIDENCE = "general_evidence"          # Fallback general evidence


class ExtractionStatus(StrEnum):
    """Lifecycle status of document processing."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    STRUCTURED = "structured"
    FAILED = "failed"


class ExtractionMethod(StrEnum):
    """Method used to extract text."""

    EMBEDDED_TEXT = "embedded_text"
    OCR = "ocr"
    HYBRID = "hybrid"
    FALLBACK = "fallback"


class ProvenancedField(BaseModel):
    """A single extracted field with source grounding, confidence, and page reference."""

    value: str | None = None
    filename: str = ""
    page: int = 1
    confidence: float = 1.0
    is_inferred: bool = False
    source_excerpt: str | None = None

    def __str__(self) -> str:
        return self.value or ""

    def citation(self) -> str:
        if not self.filename:
            return ""
        return f"[Uploaded document: {self.filename}, Page {self.page}]"


class ProvenancedItem(BaseModel):
    """An extracted list item with page-level provenance and confidence."""

    text: str
    filename: str = ""
    page: int = 1
    confidence: float = 1.0
    is_inferred: bool = False
    source_excerpt: str | None = None

    def __str__(self) -> str:
        return self.text

    def citation(self) -> str:
        if not self.filename:
            return ""
        return f"[Uploaded document: {self.filename}, Page {self.page}]"


class ExtractedTrack(BaseModel):
    """A discovered track from an uploaded document with description and rules."""

    name: str
    description: str | None = None
    track_rules: str | None = None
    official_track_url: str | None = None
    source_filename: str = ""
    source_page: int = 1
    confidence: float = 1.0
    is_inferred: bool = False

    def citation(self) -> str:
        if not self.source_filename:
            return ""
        return f"[Uploaded document: {self.source_filename}, Page {self.source_page}]"


class ExtractedConflict(BaseModel):
    """A detected conflict between uploaded documents."""

    field: str
    item_a: str
    source_a: str
    item_b: str
    source_b: str
    explanation: str


class MissingInfoStatus(BaseModel):
    """Audit of essential vs non-essential information extracted from documents."""

    is_ready_for_research: bool = True
    is_hackathon_event: bool = True
    missing_essential: list[str] = Field(default_factory=list)
    missing_optional: list[str] = Field(default_factory=list)
    suggested_action: str = ""


class DocumentChunk(BaseModel):
    """A granular, searchable chunk of an extracted document with provenance."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    document_id: str
    session_id: str | None = None
    page_number: int = 1
    chunk_index: int = 0
    content_type: str = "text"  # 'text', 'table', 'heading', 'list'
    text_content: str
    tables: list[list[str]] = Field(default_factory=list)
    extraction_method: ExtractionMethod = ExtractionMethod.EMBEDDED_TEXT
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utc_now)

    def citation(self, filename: str) -> str:
        """Standardized, verifiable citation for final reports and agent reasoning."""
        return f"[Uploaded document: {filename}, Page {self.page_number}]"


class DocumentPage(BaseModel):
    """An extracted page of a multi-page document."""

    page_number: int
    text_content: str = ""
    tables: list[list[str]] = Field(default_factory=list)
    has_images: bool = False
    is_scanned: bool = False
    extraction_method: ExtractionMethod = ExtractionMethod.EMBEDDED_TEXT
    confidence: float = 1.0
    warnings: list[str] = Field(default_factory=list)


class UploadedDocument(BaseModel):
    """Metadata and status of an uploaded document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str | None = None
    filename: str
    file_type: str  # 'pdf' or 'image'
    file_size: int
    file_hash: str
    document_type: DocumentType = DocumentType.GENERAL_EVIDENCE
    page_count: int = 1
    extraction_method: ExtractionMethod = ExtractionMethod.EMBEDDED_TEXT
    status: ExtractionStatus = ExtractionStatus.UPLOADED
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class StructuredHackathonDoc(BaseModel):
    """Structured information extracted from official hackathon rulebooks/guidelines."""

    hackathon_name: str | None = None
    organizer: str | None = None
    official_website: str | None = None
    official_rules_url: str | None = None
    theme: str | None = None
    tracks: list[str] = Field(default_factory=list)
    problem_statements: list[str] = Field(default_factory=list)
    judging_criteria: list[str] = Field(default_factory=list)
    eligibility_requirements: list[str] = Field(default_factory=list)
    submission_requirements: list[str] = Field(default_factory=list)
    important_deadlines: list[str] = Field(default_factory=list)
    event_duration: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    submission_deadline: str | None = None
    geographic_restrictions: list[str] = Field(default_factory=list)
    technical_restrictions: list[str] = Field(default_factory=list)
    required_technologies: list[str] = Field(default_factory=list)
    sponsor_requirements: list[str] = Field(default_factory=list)
    required_deliverables: list[str] = Field(default_factory=list)
    available_datasets: list[str] = Field(default_factory=list)
    legal_ethical_constraints: list[str] = Field(default_factory=list)
    evaluation_conditions: list[str] = Field(default_factory=list)
    contact_and_reference_info: list[str] = Field(default_factory=list)

    # Detailed provenanced representations
    provenanced_fields: dict[str, ProvenancedField] = Field(default_factory=dict)
    provenanced_items: dict[str, list[ProvenancedItem]] = Field(default_factory=dict)
    extracted_tracks: list[ExtractedTrack] = Field(default_factory=list)
    conflicts: list[ExtractedConflict] = Field(default_factory=list)

    extracted_facts: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    unverified_items: list[str] = Field(default_factory=list)

    def get_field_provenance(self, field_name: str) -> ProvenancedField | None:
        """Get provenance record for a specific field."""
        return self.provenanced_fields.get(field_name)

    def get_items_provenance(self, category: str) -> list[ProvenancedItem]:
        """Get provenance list for a category."""
        return self.provenanced_items.get(category, [])


class StructuredResearchDoc(BaseModel):
    """Structured evidence extracted from research papers, reports or civic datasets."""

    document_title: str | None = None
    authors_or_institution: str | None = None
    publication_date: str | None = None
    key_findings: list[str] = Field(default_factory=list)
    problems_identified: list[str] = Field(default_factory=list)
    target_geography: str | None = None
    datasets_and_methodologies: list[str] = Field(default_factory=list)
    existing_solutions_noted: list[str] = Field(default_factory=list)
    technical_feasibility_insights: list[str] = Field(default_factory=list)
    limitations_and_gaps: list[str] = Field(default_factory=list)

    provenanced_fields: dict[str, ProvenancedField] = Field(default_factory=dict)
    provenanced_items: dict[str, list[ProvenancedItem]] = Field(default_factory=dict)

    extracted_facts: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    unverified_items: list[str] = Field(default_factory=list)


class DocumentSearchHit(BaseModel):
    """A search result retrieved from document chunks for agent consumption."""

    chunk_id: str
    document_id: str
    filename: str
    document_type: DocumentType = DocumentType.GENERAL_EVIDENCE
    page_number: int
    chunk_index: int = 0
    content_type: str = "text"
    text_content: str
    extraction_method: str = "embedded_text"
    confidence: float = 1.0
    rank: float = 1.0
    citation: str = ""

    def as_evidence_context(self, index: int) -> str:
        """Render for injection into prompt context."""
        cite = self.citation or f"[Uploaded document: {self.filename}, Page {self.page_number}]"
        return f"[DOC-{index}] ({cite}, Type: {self.document_type.value})\n{self.text_content.strip()[:1000]}"
