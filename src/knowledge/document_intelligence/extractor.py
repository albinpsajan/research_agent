"""Core file validation, text extraction, OCR engine and table/layout analysis."""

from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
from pathlib import Path
from typing import Any

from config.logging_config import get_logger
from src.knowledge.document_intelligence.models import (
    DocumentChunk,
    DocumentPage,
    ExtractionMethod,
)

logger = get_logger("knowledge.document_intelligence.extractor")

MAGIC_HEADERS: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".webp": (b"RIFF",),  # Also checked for WEBP fourcc below
}


class ExtractionError(RuntimeError):
    """Raised when an uploaded document cannot be read or processed."""


def sanitize_filename(filename: str) -> str:
    """Strip directory traversal, unsafe characters, and bound length."""
    base = Path(filename).name
    cleaned = re.sub(r"[^\w\-. ]", "_", base).strip(" .")
    if not cleaned:
        cleaned = "uploaded_document"
    return cleaned[:120]


def validate_uploaded_file(
    filename: str,
    file_bytes: bytes,
    max_file_size_mb: int = 25,
    supported_extensions: list[str] | None = None,
) -> tuple[str, str, str]:
    """Validate file extension, size, and magic bytes.

    Returns:
        (sanitized_filename, file_type, file_hash)
    """
    if not file_bytes:
        raise ExtractionError("Uploaded file is empty (0 bytes)")

    max_bytes = max_file_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise ExtractionError(
            f"File exceeds maximum size of {max_file_size_mb} MB (actual: {len(file_bytes) / 1024 / 1024:.2f} MB)"
        )

    safe_name = sanitize_filename(filename)
    ext = Path(safe_name).suffix.lower()

    valid_exts = supported_extensions or [".pdf", ".jpg", ".jpeg", ".png", ".webp"]
    if ext not in valid_exts:
        raise ExtractionError(
            f"Unsupported file format '{ext}'. Allowed formats: {', '.join(valid_exts)}"
        )

    # Magic byte validation
    expected_magics = MAGIC_HEADERS.get(ext, ())
    matched = False
    for magic in expected_magics:
        if file_bytes.startswith(magic):
            if ext == ".webp":
                # Ensure 'WEBP' is at byte offset 8
                if len(file_bytes) >= 12 and file_bytes[8:12] == b"WEBP":
                    matched = True
                    break
            else:
                matched = True
                break

    if not matched:
        raise ExtractionError(
            f"File header does not match declared extension '{ext}' (possible corrupted or disguised file)"
        )

    file_type = "pdf" if ext == ".pdf" else "image"
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    return safe_name, file_type, file_hash


class OCREngine:
    """Local, offline-capable OCR wrapper around Tesseract with graceful fallback."""

    def __init__(self, tesseract_cmd: str | None = None, timeout_seconds: int = 30) -> None:
        self.tesseract_cmd = tesseract_cmd or os.getenv("TESSERACT_CMD")
        self.timeout_seconds = timeout_seconds
        self._available: bool | None = None
        self._mock_handler: Any = None

    def set_mock_handler(self, handler: Any) -> None:
        """Testing hook to simulate OCR without system binaries."""
        self._mock_handler = handler

    def is_available(self) -> bool:
        """Check whether local Tesseract OCR is operational."""
        if self._mock_handler is not None:
            return True
        if self._available is not None:
            return self._available

        try:
            import pytesseract

            cmd = self.tesseract_cmd or shutil.which("tesseract")
            if not cmd:
                # Check standard Windows installation paths
                win_paths = [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
                ]
                for p in win_paths:
                    if os.path.exists(p):
                        cmd = p
                        break

            if cmd and os.path.exists(cmd):
                pytesseract.pytesseract.tesseract_cmd = cmd
                self.tesseract_cmd = cmd
                self._available = True
                logger.info("Local Tesseract-OCR binary found: %s", cmd)
            elif shutil.which("tesseract"):
                self._available = True
            else:
                self._available = False
                logger.info("Tesseract-OCR binary not detected on Windows host.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error checking Tesseract OCR availability: %s", exc)
            self._available = False

        return self._available

    def extract_text_from_image(self, image_bytes: bytes) -> tuple[str, float, list[str]]:
        """Run OCR on image bytes.

        Returns:
            (extracted_text, confidence, warnings)
        """
        if self._mock_handler is not None:
            return self._mock_handler(image_bytes)

        if not self.is_available():
            msg = (
                "Local Tesseract-OCR executable is not installed on this system. "
                "Embedded metadata was extracted, but image text requires Tesseract. "
                "(Windows install: `winget install UB-Mannheim.TesseractOCR`)"
            )
            return "", 0.0, [msg]

        try:
            import pytesseract
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))
            # Convert to grayscale for cleaner OCR contrast
            if img.mode not in ("L", "RGB"):
                img = img.convert("RGB")

            text = pytesseract.image_to_string(img, timeout=self.timeout_seconds)
            cleaned = text.strip()
            confidence = 0.85 if len(cleaned) > 20 else 0.5
            return cleaned, confidence, []
        except Exception as exc:  # noqa: BLE001
            logger.warning("OCR extraction failed on image: %s", exc)
            return "", 0.0, [f"OCR extraction failed: {exc}"]


class DocumentExtractor:
    """Extracts text, structure, tables, and page metadata from PDFs and images."""

    def __init__(
        self,
        ocr_engine: OCREngine | None = None,
        max_pages: int = 50,
    ) -> None:
        self.ocr = ocr_engine or OCREngine()
        self.max_pages = max_pages

    def extract_document(
        self,
        document_id: str,
        filename: str,
        file_bytes: bytes,
        file_type: str,
        session_id: str | None = None,
    ) -> tuple[list[DocumentPage], list[DocumentChunk], list[str], ExtractionMethod]:
        """Complete extraction pipeline for PDF or image bytes.

        Returns:
            (pages, chunks, global_warnings, overall_extraction_method)
        """
        if file_type == "pdf":
            return self._extract_pdf(document_id, filename, file_bytes, session_id)
        return self._extract_image(document_id, filename, file_bytes, session_id)

    def _extract_pdf(
        self,
        document_id: str,
        filename: str,
        file_bytes: bytes,
        session_id: str | None,
    ) -> tuple[list[DocumentPage], list[DocumentChunk], list[str], ExtractionMethod]:
        try:
            import pypdf
        except ImportError as exc:
            raise ExtractionError("pypdf package is required for PDF extraction") from exc

        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        except Exception as exc:
            raise ExtractionError(f"Corrupted or invalid PDF structure: {exc}") from exc

        total_pages = len(reader.pages)
        if total_pages == 0:
            raise ExtractionError("PDF document contains 0 pages")

        pages: list[DocumentPage] = []
        chunks: list[DocumentChunk] = []
        global_warnings: list[str] = []
        methods_used: set[ExtractionMethod] = set()

        effective_pages = min(total_pages, self.max_pages)
        if total_pages > self.max_pages:
            global_warnings.append(
                f"Document exceeds maximum page limit ({self.max_pages} pages). Only the first {self.max_pages} pages were processed."
            )

        for page_idx in range(effective_pages):
            page_num = page_idx + 1
            page_obj = reader.pages[page_idx]
            page_warnings: list[str] = []

            # 1. Extract embedded text
            try:
                extracted_raw = page_obj.extract_text() or ""
            except Exception as exc:  # noqa: BLE001
                extracted_raw = ""
                page_warnings.append(f"Embedded text extraction error: {exc}")

            # Check if page contains images
            has_images = bool(getattr(page_obj, "images", []))
            alpha_tokens = [t for t in re.split(r"\s+", extracted_raw) if len(t) > 1 and any(c.isalnum() for c in t)]

            # Detect scanned page (almost no embedded text, but images exist)
            is_scanned = len(alpha_tokens) < 5 and has_images
            page_text = extracted_raw.strip()
            method = ExtractionMethod.EMBEDDED_TEXT
            confidence = 0.95

            if is_scanned:
                method = ExtractionMethod.OCR
                methods_used.add(ExtractionMethod.OCR)
                # Attempt OCR on page images
                ocr_texts: list[str] = []
                for img_obj in page_obj.images:
                    try:
                        img_bytes = img_obj.data
                        img_text, ocr_conf, ocr_warns = self.ocr.extract_text_from_image(img_bytes)
                        if img_text:
                            ocr_texts.append(img_text)
                        page_warnings.extend(ocr_warns)
                        confidence = min(confidence, ocr_conf)
                    except Exception as ocr_exc:  # noqa: BLE001
                        page_warnings.append(f"Failed OCR on page image: {ocr_exc}")

                if ocr_texts:
                    page_text = "\n\n".join(ocr_texts).strip()
                elif not page_text:
                    confidence = 0.2
                    page_warnings.append("Scanned page detected, but no readable text could be recovered via OCR.")
            else:
                methods_used.add(ExtractionMethod.EMBEDDED_TEXT)

            # Table extraction heuristic from embedded text
            tables = self._extract_tables_from_text(page_text)

            page_record = DocumentPage(
                page_number=page_num,
                text_content=page_text,
                tables=tables,
                has_images=has_images,
                is_scanned=is_scanned,
                extraction_method=method,
                confidence=confidence,
                warnings=page_warnings,
            )
            pages.append(page_record)

            # Create granular chunks for this page
            page_chunks = self._chunk_page_text(
                document_id=document_id,
                session_id=session_id,
                page_num=page_num,
                text=page_text,
                tables=tables,
                method=method,
                confidence=confidence,
            )
            chunks.extend(page_chunks)

        overall_method = (
            ExtractionMethod.HYBRID
            if len(methods_used) > 1
            else next(iter(methods_used), ExtractionMethod.EMBEDDED_TEXT)
        )

        return pages, chunks, global_warnings, overall_method

    def _extract_image(
        self,
        document_id: str,
        filename: str,
        file_bytes: bytes,
        session_id: str | None,
    ) -> tuple[list[DocumentPage], list[DocumentChunk], list[str], ExtractionMethod]:
        warnings: list[str] = []
        text, confidence, ocr_warns = self.ocr.extract_text_from_image(file_bytes)
        warnings.extend(ocr_warns)

        tables = self._extract_tables_from_text(text)

        page = DocumentPage(
            page_number=1,
            text_content=text,
            tables=tables,
            has_images=True,
            is_scanned=True,
            extraction_method=ExtractionMethod.OCR,
            confidence=confidence,
            warnings=warnings,
        )

        chunks = self._chunk_page_text(
            document_id=document_id,
            session_id=session_id,
            page_num=1,
            text=text,
            tables=tables,
            method=ExtractionMethod.OCR,
            confidence=confidence,
        )

        return [page], chunks, warnings, ExtractionMethod.OCR

    def _extract_tables_from_text(self, text: str) -> list[list[str]]:
        """Identify tabular rows delineated by pipes, tabs, or aligned columns."""
        tables: list[list[str]] = []
        lines = text.splitlines()
        current_table: list[str] = []

        for line in lines:
            line_str = line.strip()
            # Pipe-separated table row (e.g. | Col 1 | Col 2 |)
            if line_str.startswith("|") and line_str.endswith("|"):
                cells = [c.strip() for c in line_str.split("|")[1:-1]]
                if any(cells) and not all(set(c) <= {"-", ":", " "} for c in cells):
                    current_table.append(" | ".join(cells))
            elif "\t" in line_str:
                cells = [c.strip() for c in line_str.split("\t") if c.strip()]
                if len(cells) >= 2:
                    current_table.append(" | ".join(cells))
            else:
                if len(current_table) >= 2:
                    tables.append(list(current_table))
                current_table = []

        if len(current_table) >= 2:
            tables.append(list(current_table))

        return tables

    def _chunk_page_text(
        self,
        document_id: str,
        session_id: str | None,
        page_num: int,
        text: str,
        tables: list[list[str]],
        method: ExtractionMethod,
        confidence: float,
        target_chunk_size: int = 800,
    ) -> list[DocumentChunk]:
        """Split page text into cohesive, structured paragraphs/chunks."""
        chunks: list[DocumentChunk] = []
        if not text.strip() and not tables:
            return chunks

        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]

        current_buf: list[str] = []
        current_len = 0
        chunk_idx = 0

        for para in paragraphs:
            para_len = len(para)
            if current_len + para_len > target_chunk_size and current_buf:
                chunk_text = "\n\n".join(current_buf).strip()
                chunks.append(
                    DocumentChunk(
                        document_id=document_id,
                        session_id=session_id,
                        page_number=page_num,
                        chunk_index=chunk_idx,
                        content_type="text",
                        text_content=chunk_text,
                        extraction_method=method,
                        confidence=confidence,
                    )
                )
                chunk_idx += 1
                current_buf = [para]
                current_len = para_len
            else:
                current_buf.append(para)
                current_len += para_len

        if current_buf:
            chunk_text = "\n\n".join(current_buf).strip()
            chunks.append(
                DocumentChunk(
                    document_id=document_id,
                    session_id=session_id,
                    page_number=page_num,
                    chunk_index=chunk_idx,
                    content_type="text",
                    text_content=chunk_text,
                    extraction_method=method,
                    confidence=confidence,
                )
            )
            chunk_idx += 1

        # If tables were detected, append them as dedicated structured table chunks
        for t_idx, tbl in enumerate(tables):
            table_text = "TABLE STRUCTURE:\n" + "\n".join(tbl)
            chunks.append(
                DocumentChunk(
                    document_id=document_id,
                    session_id=session_id,
                    page_number=page_num,
                    chunk_index=chunk_idx + t_idx,
                    content_type="table",
                    text_content=table_text,
                    tables=[[row] for row in tbl],
                    extraction_method=method,
                    confidence=confidence,
                )
            )

        return chunks


def sanitize_for_prompt_injection(text: str, filename: str, page_number: int) -> str:
    """Encapsulate untrusted document content in protective boundary tags.

    Guards against indirect prompt injections embedded in uploaded PDFs/images
    that attempt to alter agent goals or ignore system rules.
    """
    cleaned = text.replace("</untrusted_document_content>", "[ESCAPED_TAG]")
    return (
        f'<untrusted_document_content filename="{filename}" page="{page_number}">\n'
        f"{cleaned}\n"
        f"</untrusted_document_content>"
    )
