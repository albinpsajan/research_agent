"""Document Intelligence Service — Orchestrates upload, extraction, LLM structuring, storage and retrieval."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from config.logging_config import get_logger
from config.settings import get_settings
from src.database.repository import Repository
from src.knowledge.document_intelligence.auto_configurator import (
    HackathonAutoConfigurator,
)
from src.knowledge.document_intelligence.classifier import DocumentClassifier
from src.knowledge.document_intelligence.consolidator import DocumentConsolidator
from src.knowledge.document_intelligence.extractor import (
    DocumentExtractor,
    ExtractionError,
    OCREngine,
    sanitize_for_prompt_injection,
    validate_uploaded_file,
)
from src.knowledge.document_intelligence.models import (
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
from src.llm.client import LLMClientProtocol, OllamaClient
from src.models.hackathon import HackathonInput, MultiTrackMode
from src.models.pipeline import PipelineOptions

if TYPE_CHECKING:
    from src.models.multitrack import MultiTrackPipelineResult
    from src.models.pipeline import PipelineResult

logger = get_logger("knowledge.document_intelligence.service")

HACKATHON_STRUCTURING_SYSTEM = """You are the HackathonIQ Document Intelligence Analyzer.
Analyze the provided uploaded hackathon document excerpts.
Extract strictly verified facts, official rules, judging criteria and constraints.
Distinguish:
- extracted_facts: statements explicitly written in the text.
- inferences: reasonable conclusions drawn from the facts.
- unverified_items: ambiguous or incomplete details.
Return ONLY valid JSON matching the requested schema. Never invent facts."""

RESEARCH_STRUCTURING_SYSTEM = """You are the HackathonIQ Scientific & Evidence Document Analyzer.
Analyze the provided uploaded research paper, government report or dataset documentation.
Extract key findings, problems identified, target geography, methodologies and feasibility insights.
Distinguish:
- extracted_facts: findings directly stated in the text.
- inferences: contextual deductions.
- unverified_items: preliminary or unvalidated claims.
Return ONLY valid JSON matching the requested schema. Never invent facts."""


class DocumentIntelligenceService:
    """Service providing document upload, extraction, structured LLM analysis, and agent evidence retrieval."""

    def __init__(
        self,
        repository: Repository | None = None,
        llm: LLMClientProtocol | None = None,
        extractor: DocumentExtractor | None = None,
        uploads_dir: Path | None = None,
    ) -> None:
        self.settings = get_settings()
        self.repository = repository or Repository()
        self.llm = llm or OllamaClient(self.settings.ollama)
        self.uploads_dir = uploads_dir or Path(self.settings.storage.uploads_dir)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.extractor = extractor or DocumentExtractor(
            ocr_engine=OCREngine(tesseract_cmd=self.settings.document_intelligence.tesseract_cmd),
            max_pages=self.settings.document_intelligence.max_pages_per_doc,
        )
        self.classifier = DocumentClassifier(llm=self.llm)

    def upload_document(
        self,
        filename: str,
        file_bytes: bytes,
        document_type: DocumentType = DocumentType.GENERAL_EVIDENCE,
        session_id: str | None = None,
        extract_structured: bool = True,
    ) -> UploadedDocument:
        """Process an uploaded document from start to finish."""
        safe_name, file_type, file_hash = validate_uploaded_file(
            filename,
            file_bytes,
            max_file_size_mb=self.settings.document_intelligence.max_file_size_mb,
            supported_extensions=self.settings.document_intelligence.supported_extensions,
        )

        # Duplicate detection by SHA-256
        existing = self.repository.get_uploaded_document_by_hash(file_hash)
        if existing:
            logger.info("Identical document already ingested: %s (hash: %s)", safe_name, file_hash[:8])
            # Re-associate with current session if provided
            doc = UploadedDocument(
                id=existing["id"],
                session_id=session_id or existing.get("session_id"),
                filename=existing["filename"],
                file_type=existing["file_type"],
                file_size=existing["file_size"],
                file_hash=existing["file_hash"],
                document_type=DocumentType(existing["document_type"]),
                page_count=existing["page_count"],
                extraction_method=ExtractionMethod(existing["extraction_method"]),
                status=ExtractionStatus(existing["status"]),
                warnings=existing.get("warnings", []) + ["Document content already exists; reused verified extraction."],
                metadata=existing.get("metadata", {}),
                is_active=bool(existing.get("is_active", 1)),
            )
            return doc

        doc_id = str(uuid4())
        stored_path = self.uploads_dir / f"{doc_id}_{safe_name}"
        try:
            stored_path.write_bytes(file_bytes)
        except OSError as exc:
            logger.warning("Could not persist file to disk: %s", exc)

        # Initial database record
        self.repository.save_uploaded_document(
            doc_id=doc_id,
            filename=safe_name,
            file_type=file_type,
            file_size=len(file_bytes),
            file_hash=file_hash,
            document_type=document_type.value,
            page_count=1,
            extraction_method=ExtractionMethod.EMBEDDED_TEXT.value,
            status=ExtractionStatus.PROCESSING.value,
            session_id=session_id,
            warnings=[],
            metadata={"stored_path": str(stored_path)},
        )

        # Run extraction
        try:
            pages, chunks, warnings, method = self.extractor.extract_document(
                document_id=doc_id,
                filename=safe_name,
                file_bytes=file_bytes,
                file_type=file_type,
                session_id=session_id,
            )

            # Save chunks to DB (with FTS5 indexing)
            chunk_dicts = [c.model_dump() for c in chunks]
            self.repository.save_document_chunks(chunk_dicts)

            # Auto-classify document if default GENERAL_EVIDENCE was passed
            if document_type == DocumentType.GENERAL_EVIDENCE and pages:
                all_text = "\n".join(p.text_content for p in pages[:4])
                detected_type, conf = self.classifier.classify_document(
                    filename=safe_name,
                    full_text=all_text,
                )
                if conf >= 0.70:
                    document_type = detected_type
                    logger.info("Auto-classified '%s' as %s (confidence: %.2f)", safe_name, detected_type.value, conf)

            status = ExtractionStatus.EXTRACTED
            self.repository.update_document_status(
                doc_id=doc_id,
                status=status.value,
                warnings=warnings,
                page_count=len(pages),
                extraction_method=method.value,
            )

            # Optional structured extraction via LLM
            if extract_structured and chunks:
                try:
                    self.extract_structured_intelligence(doc_id, document_type, session_id=session_id)
                    status = ExtractionStatus.STRUCTURED
                    self.repository.update_document_status(doc_id=doc_id, status=status.value)
                except Exception as llm_exc:  # noqa: BLE001
                    logger.warning("Structured extraction failed: %s", llm_exc)
                    warnings.append(f"Structured analysis warning: {llm_exc}")
                    self.repository.update_document_status(doc_id=doc_id, status=ExtractionStatus.EXTRACTED.value, warnings=warnings)

            return UploadedDocument(
                id=doc_id,
                session_id=session_id,
                filename=safe_name,
                file_type=file_type,
                file_size=len(file_bytes),
                file_hash=file_hash,
                document_type=document_type,
                page_count=len(pages),
                extraction_method=method,
                status=status,
                warnings=warnings,
                metadata={"stored_path": str(stored_path)},
                is_active=True,
            )

        except Exception as exc:
            logger.error("Failed to extract document '%s': %s", safe_name, exc)
            self.repository.update_document_status(
                doc_id=doc_id,
                status=ExtractionStatus.FAILED.value,
                warnings=[f"Extraction failed: {exc}"],
            )
            raise ExtractionError(f"Failed to extract text from '{safe_name}': {exc}") from exc

    def extract_structured_intelligence(
        self,
        doc_id: str,
        document_type: DocumentType,
        session_id: str | None = None,
    ) -> StructuredHackathonDoc | StructuredResearchDoc:
        """Run Ollama model over top chunks to extract structured intelligence."""
        chunks = self.repository.get_document_chunks(doc_id)
        if not chunks:
            raise ExtractionError(f"No text chunks found for document ID {doc_id}")

        doc = self.repository.get_uploaded_document(doc_id)
        filename = doc["filename"] if doc else "uploaded_document"

        # Assemble up to ~7,000 characters from first chunks with prompt injection defense
        chunk_texts: list[str] = []
        for ch in chunks[:12]:
            safe_text = sanitize_for_prompt_injection(
                ch["text_content"],
                filename=filename,
                page_number=ch["page_number"],
            )
            chunk_texts.append(safe_text)

        document_context = "\n\n".join(chunk_texts)[:7500]

        if document_type in (DocumentType.OFFICIAL_RULES, DocumentType.EVENT_ANNOUNCEMENT, DocumentType.TRACK_DESCRIPTION):
            prompt = f"""DOCUMENT: {filename}
{document_context}

Analyze this official hackathon document. Extract all rules, tracks, eligibility, deadlines, constraints, and criteria.
Ensure all extracted facts are strictly grounded in the document text."""

            try:
                res = self.llm.generate_json(prompt, StructuredHackathonDoc, HACKATHON_STRUCTURING_SYSTEM)
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM hackathon structuring failed, using partial fallback: %s", exc)
                res = StructuredHackathonDoc(
                    hackathon_name=filename.replace(".pdf", "").replace("_", " "),
                    extracted_facts=[f"Document: {filename} containing {len(chunks)} extracted chunks."],
                    unverified_items=[f"Automatic LLM structuring encountered error: {exc}"],
                )

            # Ground scalar field provenance with current document filename
            for f_name in ("hackathon_name", "organizer", "official_website", "theme", "submission_deadline", "event_duration", "start_date", "end_date"):
                val = getattr(res, f_name, None)
                if val:
                    res.provenanced_fields[f_name] = ProvenancedField(
                        value=str(val),
                        filename=filename,
                        page=1,
                        confidence=0.92,
                        is_inferred=False,
                    )

            # Convert tracks to ExtractedTrack if needed and ground filename
            if not res.extracted_tracks and res.tracks:
                res.extracted_tracks = [
                    ExtractedTrack(
                        name=t.strip(),
                        source_filename=filename,
                        source_page=1,
                        confidence=0.90,
                    )
                    for t in res.tracks
                    if t.strip()
                ]
            elif res.extracted_tracks:
                for t in res.extracted_tracks:
                    t.source_filename = filename
                res.tracks = [t.name for t in res.extracted_tracks]

            # Populate list items provenance
            for cat, items in (
                ("judging_criteria", res.judging_criteria),
                ("technical_restrictions", res.technical_restrictions),
                ("eligibility_requirements", res.eligibility_requirements),
                ("geographic_restrictions", res.geographic_restrictions),
                ("required_technologies", res.required_technologies),
                ("sponsor_requirements", res.sponsor_requirements),
                ("submission_requirements", res.submission_requirements),
                ("required_deliverables", res.required_deliverables),
            ):
                if items:
                    res.provenanced_items[cat] = [
                        ProvenancedItem(
                            text=str(it),
                            filename=filename,
                            page=1,
                            confidence=0.90,
                            is_inferred=False,
                        )
                        for it in items
                    ]

            self.repository.save_document_structured_extraction(
                doc_id=doc_id,
                extraction_type="hackathon_profile",
                data_json=res.model_dump_json(),
                session_id=session_id,
            )
            return res
        else:
            prompt = f"""DOCUMENT: {filename}
{document_context}

Analyze this research/evidence document. Extract findings, problem definitions, geographical scope, datasets, and feasibility."""

            try:
                res = self.llm.generate_json(prompt, StructuredResearchDoc, RESEARCH_STRUCTURING_SYSTEM)
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM research structuring failed, using partial fallback: %s", exc)
                res = StructuredResearchDoc(
                    document_title=filename,
                    extracted_facts=[f"Document: {filename} containing {len(chunks)} extracted chunks."],
                    unverified_items=[f"Automatic LLM structuring encountered error: {exc}"],
                )

            for f_name in ("document_title", "authors_or_institution", "publication_date", "target_geography"):
                val = getattr(res, f_name, None)
                if val and f_name not in res.provenanced_fields:
                    res.provenanced_fields[f_name] = ProvenancedField(
                        value=str(val),
                        filename=filename,
                        page=1,
                        confidence=0.90,
                        is_inferred=False,
                    )

            for cat, items in (
                ("key_findings", res.key_findings),
                ("problems_identified", res.problems_identified),
                ("datasets_and_methodologies", res.datasets_and_methodologies),
                ("existing_solutions_noted", res.existing_solutions_noted),
                ("technical_feasibility_insights", res.technical_feasibility_insights),
                ("limitations_and_gaps", res.limitations_and_gaps),
            ):
                if items and cat not in res.provenanced_items:
                    res.provenanced_items[cat] = [
                        ProvenancedItem(
                            text=str(it),
                            filename=filename,
                            page=1,
                            confidence=0.90,
                            is_inferred=False,
                        )
                        for it in items
                    ]

            self.repository.save_document_structured_extraction(
                doc_id=doc_id,
                extraction_type="research_evidence",
                data_json=res.model_dump_json(),
                session_id=session_id,
            )
            return res

    def search_evidence(
        self,
        query: str,
        session_id: str | None = None,
        document_ids: list[str] | None = None,
        limit: int = 6,
    ) -> list[DocumentSearchHit]:
        """Search active uploaded document chunks using FTS5 BM25 ranking."""
        rows = self.repository.search_document_chunks(
            query=query,
            session_id=session_id,
            document_ids=document_ids,
            limit=limit,
        )
        hits: list[DocumentSearchHit] = []
        for r in rows:
            filename = r.get("filename", "document")
            page_num = r.get("page_number", 1)
            citation = f"[Uploaded document: {filename}, Page {page_num}]"
            hits.append(
                DocumentSearchHit(
                    chunk_id=r["id"],
                    document_id=r["document_id"],
                    filename=filename,
                    document_type=DocumentType(r.get("document_type", "general_evidence")),
                    page_number=page_num,
                    chunk_index=r.get("chunk_index", 0),
                    content_type=r.get("content_type", "text"),
                    text_content=r.get("text_content", ""),
                    extraction_method=r.get("extraction_method", "embedded_text"),
                    confidence=float(r.get("confidence", 1.0)),
                    rank=float(r.get("rank", 1.0)),
                    citation=citation,
                )
            )
        return hits

    def get_structured_hackathon_intelligence(self, session_id: str | None = None) -> list[StructuredHackathonDoc]:
        """Retrieve all structured profiles from uploaded official rulebooks."""
        docs = self.repository.list_uploaded_documents(session_id=session_id, is_active_only=True)
        results: list[StructuredHackathonDoc] = []
        for d in docs:
            if d.get("document_type") == DocumentType.OFFICIAL_RULES.value:
                struct = self.repository.get_document_structured_extraction(d["id"])
                if struct and struct.get("data"):
                    try:
                        results.append(StructuredHackathonDoc.model_validate(struct["data"]))
                    except (ValueError, TypeError) as exc:
                        logger.debug("Failed validating structured hackathon doc: %s", exc)
        return results

    def get_conflict_warnings(self, session_id: str | None, user_constraints: str | None) -> list[str]:
        """Identify potential conflicts between uploaded official rules and user assumptions."""
        conflicts: list[str] = []
        profiles = self.get_structured_hackathon_intelligence(session_id)
        for p in profiles:
            if p.technical_restrictions and user_constraints:
                for r in p.technical_restrictions:
                    if "api" in r.lower() and "paid" in user_constraints.lower():
                        conflicts.append(
                            f"Official document specifies technical rule: '{r}'. Please ensure proposed architectures align."
                        )
        return conflicts

    def list_documents(self, session_id: str | None = None, is_active_only: bool = False) -> list[UploadedDocument]:
        """List documents in repository."""
        rows = self.repository.list_uploaded_documents(session_id=session_id, is_active_only=is_active_only)
        result: list[UploadedDocument] = []
        for r in rows:
            try:
                result.append(
                    UploadedDocument(
                        id=r["id"],
                        session_id=r.get("session_id"),
                        filename=r["filename"],
                        file_type=r["file_type"],
                        file_size=r["file_size"],
                        file_hash=r["file_hash"],
                        document_type=DocumentType(r.get("document_type", "general_evidence")),
                        page_count=r.get("page_count", 1),
                        extraction_method=ExtractionMethod(r.get("extraction_method", "embedded_text")),
                        status=ExtractionStatus(r.get("status", "uploaded")),
                        warnings=r.get("warnings", []),
                        metadata=r.get("metadata", {}),
                        is_active=bool(r.get("is_active", 1)),
                    )
                )
            except (ValueError, KeyError, TypeError) as exc:
                logger.warning("Error deserializing document record %s: %s", r.get("id"), exc)
        return result

    def delete_document(self, doc_id: str) -> bool:
        """Permanently delete document and clean up local stored file."""
        doc = self.repository.get_uploaded_document(doc_id)
        if doc and doc.get("metadata", {}).get("stored_path"):
            try:
                p = Path(doc["metadata"]["stored_path"])
                if p.exists():
                    p.unlink()
            except OSError as exc:
                logger.warning("Failed to remove stored file: %s", exc)
        return self.repository.delete_uploaded_document(doc_id)

    def set_document_active(self, doc_id: str, is_active: bool) -> None:
        """Toggle active context participation."""
        self.repository.set_document_active(doc_id, is_active)

    def retry_extraction(self, doc_id: str) -> UploadedDocument:
        """Retry extraction for a previously failed or pending document."""
        doc = self.repository.get_uploaded_document(doc_id)
        if not doc:
            raise ExtractionError(f"Document ID {doc_id} not found")

        stored_path = doc.get("metadata", {}).get("stored_path")
        if not stored_path or not Path(stored_path).exists():
            raise ExtractionError(f"Stored binary file missing for document {doc['filename']}")

        file_bytes = Path(stored_path).read_bytes()
        # Delete old chunks
        self.repository.delete_uploaded_document(doc_id)
        # Re-upload
        return self.upload_document(
            filename=doc["filename"],
            file_bytes=file_bytes,
            document_type=DocumentType(doc["document_type"]),
            session_id=doc.get("session_id"),
        )

    def consolidate_session_documents(
        self, session_id: str | None = None
    ) -> tuple[StructuredHackathonDoc, list[ExtractedConflict]]:
        """Consolidate multiple hackathon profiles into one unified profile with conflict detection."""
        docs = self.list_documents(session_id=session_id, is_active_only=True)
        profiles_to_merge: list[tuple[StructuredHackathonDoc, str, DocumentType]] = []
        for d in docs:
            struct = self.repository.get_document_structured_extraction(d.id)
            if struct and struct.get("data"):
                try:
                    prof = StructuredHackathonDoc.model_validate(struct["data"])
                    profiles_to_merge.append((prof, d.filename, d.document_type))
                except (ValueError, TypeError) as exc:
                    logger.debug("Failed validating structured hackathon doc for %s: %s", d.filename, exc)

        return DocumentConsolidator.consolidate_hackathon_profiles(profiles_to_merge)

    def auto_configure_hackathon(
        self,
        session_id: str | None = None,
        mode: MultiTrackMode = MultiTrackMode.BEST_OVERALL,
        user_overrides: dict[str, Any] | None = None,
    ) -> tuple[HackathonInput | None, MissingInfoStatus, list[ExtractedConflict], StructuredHackathonDoc]:
        """Automatically builds HackathonInput configuration from all active uploaded documents."""
        docs = self.list_documents(session_id=session_id, is_active_only=True)
        profile, _conflicts = self.consolidate_session_documents(session_id=session_id)
        hackathon_input, status, all_conflicts = HackathonAutoConfigurator.configure_hackathon(
            profile=profile,
            documents=docs,
            multi_track_mode=mode,
            user_overrides=user_overrides,
        )
        return hackathon_input, status, all_conflicts, profile

    def execute_automated_research(
        self,
        hackathon_input: HackathonInput,
        options: PipelineOptions | None = None,
        session_id: str | None = None,
        progress_callback: Callable[[str, str, float], None] | None = None,
    ) -> PipelineResult | MultiTrackPipelineResult:
        """Execute the complete five-agent HackathonIQ research pipeline automatically."""
        from src.orchestration.pipeline import HackathonPipeline

        pipeline = HackathonPipeline(
            repository=self.repository,
            llm=self.llm,
            progress=progress_callback,
        )

        options = options or PipelineOptions()

        if hackathon_input.is_multi_track and hackathon_input.tracks:
            return pipeline.run_multi_track(hackathon_input, options, session_id=session_id)
        return pipeline.run(hackathon_input, options, session_id=session_id)
