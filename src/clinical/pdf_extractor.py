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


class GeminiOcrExtractor(PdfExtractorBase):
    """Real OCR extractor using Gemini API."""
    
    OCR_ENGINE = "gemini-ocr"
    OCR_ENGINE_VERSION = "gemini-2.5-flash"
    
    def __init__(self, api_key: str):
        self._api_key = api_key
        
    def extract(self, content: bytes, document_id: str) -> DocumentExtraction:
        import json
        import logging
        logger = logging.getLogger(__name__)
        
        checksum = _sha256(content)
        
        if not self._api_key or not self._api_key.startswith("AIza"):
            logger.warning("No valid Gemini API key for Gemini OCR; falling back to empty extraction")
            return DocumentExtraction(
                document_id=document_id,
                page_count=1,
                pages=[],
                source_checksum=checksum,
                extraction_version=EXTRACTION_VERSION,
                has_text_layer=False,
            )
            
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=self._api_key)
            
            # Detect mime type based on magic bytes
            mime_type = "application/pdf"
            if content.startswith(b"\x89PNG"):
                mime_type = "image/png"
            elif content.startswith(b"\xff\xd8"):
                mime_type = "image/jpeg"
                
            prompt = (
                "Extract all clinical text and data from this medical document accurately.\n"
                "Return a structured JSON object with:\n"
                "- 'markdown': faithful reconstructed Markdown text of the entire document (tables, headings, values)\n"
                "- 'blocks': array of objects with 'text' and 'confidence' (float 0.8-1.0)."
            )
            
            response = client.models.generate_content(
                model=self.OCR_ENGINE_VERSION,
                contents=[
                    types.Content(role="user", parts=[
                        types.Part.from_bytes(data=content, mime_type=mime_type),
                        types.Part.from_text(text=prompt)
                    ])
                ],
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                )
            )
            
            raw_text = response.text or "{}"
            
            # Strip markdown json block if present
            if raw_text.startswith("```json"):
                raw_text = raw_text.strip("`").replace("json\n", "", 1)
            elif raw_text.startswith("```"):
                raw_text = raw_text.strip("`")
                
            parsed = json.loads(raw_text)
            blocks_data = parsed.get("blocks", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
            markdown_text = parsed.get("markdown", "") if isinstance(parsed, dict) else ""
            
            if not blocks_data and markdown_text:
                blocks_data = [{"text": line.strip(), "confidence": 0.95} for line in markdown_text.split("\n\n") if line.strip()]
            
            blocks = []
            full_text_parts = []
            for idx, item in enumerate(blocks_data):
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text", "")).strip()
                if not text:
                    continue
                confidence = float(item.get("confidence", 0.95))
                
                block = BlockExtraction(
                    page_number=1,
                    block_id=f"blk_{document_id}_ocr_{idx}",
                    text=text,
                    source_type="ocr",
                    ocr_confidence=confidence,
                    ocr_engine=self.OCR_ENGINE,
                    ocr_engine_version=self.OCR_ENGINE_VERSION,
                )
                blocks.append(block)
                full_text_parts.append(text)
                
            full_md = markdown_text if markdown_text else "\n\n".join(full_text_parts)
            page = PageExtraction(
                page_number=1,
                full_text=full_md,
                blocks=blocks,
                has_text_layer=False,
            )
            
            return DocumentExtraction(
                document_id=document_id,
                page_count=1,
                pages=[page] if blocks or full_md else [],
                source_checksum=checksum,
                extraction_version=EXTRACTION_VERSION,
                has_text_layer=False,
            )
            
        except Exception as exc:
            logger.warning("Gemini OCR failed: %s", exc)
            return DocumentExtraction(
                document_id=document_id,
                page_count=1,
                pages=[],
                source_checksum=checksum,
                extraction_version=EXTRACTION_VERSION,
                has_text_layer=False,
            )


class OpenAIVisionExtractor(PdfExtractorBase):
    """Vision OCR extractor using OpenAI GPT-4o / GPT-4o-mini."""

    OCR_ENGINE = "openai-vision"
    OCR_ENGINE_VERSION = "gpt-4o-mini"

    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini", base_url: str | None = None):
        self._api_key = api_key
        self._model_name = model_name or "gpt-4o-mini"
        self._base_url = base_url

    def extract(self, content: bytes, document_id: str) -> DocumentExtraction:
        import base64
        import json
        import logging
        logger = logging.getLogger(__name__)
        checksum = _sha256(content)

        if not self._api_key:
            logger.warning("No API key for OpenAI Vision; falling back to empty extraction")
            return DocumentExtraction(
                document_id=document_id,
                page_count=1,
                pages=[],
                source_checksum=checksum,
                extraction_version=EXTRACTION_VERSION,
                has_text_layer=False,
            )

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self._api_key, base_url=self._base_url or None)

            mime_type = "application/pdf"
            if content.startswith(b"\x89PNG"):
                mime_type = "image/png"
            elif content.startswith(b"\xff\xd8"):
                mime_type = "image/jpeg"

            prompt = (
                "You are an expert clinical OCR and medical document digitization system.\n"
                "Read this entire medical document accurately and completely.\n"
                "Extract all text, administrative info (patient ID, patient name, date, doc ID), "
                "diagnoses, and test results tables.\n"
                "Return a JSON object with:\n"
                "- 'markdown': full faithfully reconstructed Markdown text representing the entire document (including tables with columns: Xét nghiệm, Kết quả, Đơn vị, Tham chiếu, Cờ)\n"
                "- 'blocks': array of objects, each with 'text' (string block) and 'confidence' (float between 0.85 and 1.0)"
            )

            b64_data = base64.b64encode(content).decode("utf-8")
            data_url = f"data:{mime_type};base64,{b64_data}"

            if mime_type.startswith("image/"):
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ]
            else:
                messages = [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ]

            response = client.chat.completions.create(
                model=self._model_name,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=4096,
            )

            raw_text = response.choices[0].message.content or "{}"
            parsed = json.loads(raw_text)

            blocks_data = parsed.get("blocks", []) if isinstance(parsed, dict) else []
            markdown_text = parsed.get("markdown", "") if isinstance(parsed, dict) else ""

            if not blocks_data and markdown_text:
                blocks_data = [{"text": line.strip(), "confidence": 0.95} for line in markdown_text.split("\n\n") if line.strip()]

            blocks = []
            full_text_parts = []
            for idx, item in enumerate(blocks_data):
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text", "")).strip()
                if not text:
                    continue
                confidence = float(item.get("confidence", 0.95))
                block = BlockExtraction(
                    page_number=1,
                    block_id=f"blk_{document_id}_ocr_{idx}",
                    text=text,
                    source_type="ocr",
                    ocr_confidence=confidence,
                    ocr_engine=self.OCR_ENGINE,
                    ocr_engine_version=self._model_name,
                )
                blocks.append(block)
                full_text_parts.append(text)

            full_md = markdown_text if markdown_text else "\n\n".join(full_text_parts)
            page = PageExtraction(
                page_number=1,
                full_text=full_md,
                blocks=blocks,
                has_text_layer=False,
            )

            return DocumentExtraction(
                document_id=document_id,
                page_count=1,
                pages=[page] if blocks or full_md else [],
                source_checksum=checksum,
                extraction_version=EXTRACTION_VERSION,
                has_text_layer=False,
            )
        except Exception as exc:
            logger.warning("OpenAI Vision OCR failed: %s", exc)
            return DocumentExtraction(
                document_id=document_id,
                page_count=1,
                pages=[],
                source_checksum=checksum,
                extraction_version=EXTRACTION_VERSION,
                has_text_layer=False,
            )


class UniversalVisionExtractor(PdfExtractorBase):
    """Dispatcher extractor: chooses OpenAI Vision, Gemini Vision, or TextLayerExtractor."""

    def __init__(self, api_key: str = "", model_name: str = "gpt-4o-mini", base_url: str | None = None):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url
        self.text_layer_extractor = TextLayerExtractor()

        if api_key.startswith("sk-") or "gpt" in model_name.lower():
            self.vision_extractor: PdfExtractorBase = OpenAIVisionExtractor(api_key=api_key, model_name=model_name, base_url=base_url)
        elif model_name.lower().startswith("gemini") or api_key.startswith("AIza"):
            self.vision_extractor = GeminiOcrExtractor(api_key=api_key)
        else:
            self.vision_extractor = OpenAIVisionExtractor(api_key=api_key, model_name=model_name, base_url=base_url)

    def extract(self, content: bytes, document_id: str) -> DocumentExtraction:
        if content.startswith(b"%PDF-") and detect_has_text_layer(content):
            try:
                extraction = self.text_layer_extractor.extract(content, document_id)
                if extraction.pages and any(p.blocks for p in extraction.pages):
                    return extraction
            except Exception:
                pass

        return self.vision_extractor.extract(content, document_id)

