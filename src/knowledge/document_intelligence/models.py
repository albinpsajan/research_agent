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

    OFFICIAL_RULES = "official_rules"  # Hackathon rulebook, official challenge guidelines
    RESEARCH_PAPER = "research_paper"  # Academic papers, scientific studies, whitepapers
    TECHNICAL_SPEC = "technical_spec"  # Architecture docs, API specs, developer guides
    DATASET_DOCUMENTATION = "dataset_documentation"  # Dataset dictionaries, data schema specs
    GENERAL_EVIDENCE = "general_evidence"  # Newspaper articles, government reports, community surveys


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
    theme: str | None = None
    tracks: list[str] = Field(default_factory=list)
    problem_statements: list[str] = Field(default_factory=list)
    judging_criteria: list[str] = Field(default_factory=list)
    eligibility_requirements: list[str] = Field(default_factory=list)
    submission_requirements: list[str] = Field(default_factory=list)
    important_deadlines: list[str] = Field(default_factory=list)
    event_duration: str | None = None
    technical_restrictions: list[str] = Field(default_factory=list)
    required_technologies: list[str] = Field(default_factory=list)
    sponsor_requirements: list[str] = Field(default_factory=list)
    available_datasets: list[str] = Field(default_factory=list)
    geographic_restrictions: list[str] = Field(default_factory=list)
    legal_ethical_constraints: list[str] = Field(default_factory=list)
    evaluation_conditions: list[str] = Field(default_factory=list)
    contact_and_reference_info: list[str] = Field(default_factory=list)
    extracted_facts: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    unverified_items: list[str] = Field(default_factory=list)


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
