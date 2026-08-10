"""PDF text extraction and OCR abstraction layer.

This module provides:
- TextLayerExtractor: extract text from native PDF text layer via pypdf
- OcrExtractor: abstract interface for OCR (mockable in tests)
- MockOcrExtractor: deterministic mock returning configurable confidence

Rules:
- Never call OpenAI for OCR or clinical value parsing.
- Never open the source file from agent/LLM context.
- Only the ingestion layer calls these extractors.
"""

from __future__ import annotations

import abc
import hashlib
import io
from dataclasses import dataclass, field
from typing import Any

EXTRACTION_VERSION = "pdf-extractor@1.0.0"

# Minimum OCR confidence threshold below which we mark needs_verification.
OCR_CONFIDENCE_THRESHOLD = 0.75


@dataclass
class BlockExtraction:
    """A single extracted text block from one page."""

    page_number: int  # 1-indexed
    block_id: str | None
    text: str
    char_start: int | None = None
    char_end: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    # source_type: "text_layer" or "ocr"
    source_type: str = "text_layer"
    ocr_confidence: float | None = None
    ocr_engine: str | None = None
    ocr_engine_version: str | None = None


@dataclass
class PageExtraction:
    """All extracted blocks for one page."""

    page_number: int  # 1-indexed
    full_text: str
    blocks: list[BlockExtraction] = field(default_factory=list)
    has_text_layer: bool = True


@dataclass
class DocumentExtraction:
    """Extraction result for an entire document."""

    document_id: str
    page_count: int
    pages: list[PageExtraction] = field(default_factory=list)
    source_checksum: str = ""
    extraction_version: str = EXTRACTION_VERSION
    has_text_layer: bool = True


def _sha256(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


class PdfExtractorBase(abc.ABC):
    """Abstract base class for PDF content extraction."""

    @abc.abstractmethod
    def extract(self, content: bytes, document_id: str) -> DocumentExtraction:
        """Extract text from raw PDF bytes.

        Args:
            content: Raw PDF file bytes.
            document_id: Stable document identifier (not derived from filename).

        Returns:
            DocumentExtraction with per-page text and blocks.
        """


class TextLayerExtractor(PdfExtractorBase):
    """Extract text from PDFs that have a native text layer (no OCR needed).

    Uses pypdf which is installed in the venv. Falls back gracefully if a
    page has no extractable text (returns empty block for that page).
    """

    def extract(self, content: bytes, document_id: str) -> DocumentExtraction:
        try:
            import pypdf  # noqa: PLC0415 — late import keeps module importable without pypdf
        except ImportError as exc:
            raise RuntimeError("pypdf is required for text-layer extraction") from exc

        checksum = _sha256(content)
        reader = pypdf.PdfReader(io.BytesIO(content))
        page_count = len(reader.pages)
        pages: list[PageExtraction] = []

        for page_index, page in enumerate(reader.pages):
            page_number = page_index + 1
            raw_text: str = page.extract_text() or ""
            block_id = f"blk_{document_id}_p{page_number}_0"
            block = BlockExtraction(
                page_number=page_number,
                block_id=block_id,
                text=raw_text,
                char_start=0,
                char_end=len(raw_text),
                source_type="text_layer",
                ocr_confidence=None,
            )
            pages.append(
                PageExtraction(
                    page_number=page_number,
                    full_text=raw_text,
                    blocks=[block] if raw_text.strip() else [],
                    has_text_layer=bool(raw_text.strip()),
                )
            )

        return DocumentExtraction(
            document_id=document_id,
            page_count=page_count,
            pages=pages,
            source_checksum=checksum,
            extraction_version=EXTRACTION_VERSION,
            has_text_layer=any(p.has_text_layer for p in pages),
        )


class OcrExtractorBase(PdfExtractorBase):
    """Abstract base for OCR extractors (scan/image PDFs).

    Concrete implementations inject an OCR engine; tests use MockOcrExtractor.
    The interface is designed so agents never call this directly — only the
    ingestion layer does.
    """

    OCR_ENGINE: str = "unknown"
    OCR_ENGINE_VERSION: str = "0.0.0"

    @abc.abstractmethod
    def _run_ocr(self, page_image_bytes: bytes, page_number: int) -> list[dict[str, Any]]:
        """Run OCR on a page image.

        Returns:
            List of dicts with keys: text, confidence, bbox (optional), block_id (optional)
        """


class MockOcrExtractor(OcrExtractorBase):
    """Deterministic mock OCR extractor for tests.

    Returns a single block per page with configurable text and confidence,
    so tests can assert on needs_verification vs verified behavior without
    calling a real OCR engine.
    """

    OCR_ENGINE = "mock-ocr"
    OCR_ENGINE_VERSION = "1.0.0"

    def __init__(
        self,
        mock_text: str = "Mock OCR text",
        confidence: float = 0.95,
        page_count: int = 1,
    ):
        self._mock_text = mock_text
        self._confidence = confidence
        self._page_count = page_count

    def _run_ocr(self, page_image_bytes: bytes, page_number: int) -> list[dict[str, Any]]:
        return [
            {
                "text": self._mock_text,
                "confidence": self._confidence,
                "bbox": None,
                "block_id": f"blk_ocr_p{page_number}_0",
            }
        ]

    def extract(self, content: bytes, document_id: str) -> DocumentExtraction:
        checksum = _sha256(content)
        pages: list[PageExtraction] = []
        for page_number in range(1, self._page_count + 1):
            ocr_results = self._run_ocr(content, page_number)
            blocks: list[BlockExtraction] = []
            full_text_parts: list[str] = []
            for result in ocr_results:
                text = str(result.get("text", ""))
                confidence = float(result.get("confidence", 1.0))
                bbox_raw = result.get("bbox")
                bbox: tuple[float, float, float, float] | None = (
                    tuple(bbox_raw)  # type: ignore[arg-type]
                    if isinstance(bbox_raw, (list, tuple)) and len(bbox_raw) == 4
                    else None
                )
                block = BlockExtraction(
                    page_number=page_number,
                    block_id=result.get("block_id"),
                    text=text,
                    source_type="ocr",
                    ocr_confidence=confidence,
                    ocr_engine=self.OCR_ENGINE,
                    ocr_engine_version=self.OCR_ENGINE_VERSION,
                    bbox=bbox,
                )
                blocks.append(block)
                full_text_parts.append(text)
            pages.append(
                PageExtraction(
                    page_number=page_number,
                    full_text="\n".join(full_text_parts),
                    blocks=blocks,
                    has_text_layer=False,
                )
            )
        return DocumentExtraction(
            document_id=document_id,
            page_count=self._page_count,
            pages=pages,
            source_checksum=checksum,
            extraction_version=EXTRACTION_VERSION,
            has_text_layer=False,
        )


def detect_has_text_layer(content: bytes) -> bool:
    """Heuristic: try extracting text from first page to detect text layer.

    Returns True if the PDF has extractable text on at least one page.
    Does NOT raise; returns False on any error (treat as scan/image PDF).
    """
    try:
        import pypdf  # noqa: PLC0415

        reader = pypdf.PdfReader(io.BytesIO(content))
        for page in reader.pages[:3]:  # sample first 3 pages
            text = page.extract_text() or ""
            if len(text.strip()) > 20:
                return True
        return False
    except Exception:
        return False
