"""Canonicalization of PDF extraction results into EvidenceItems with DocumentCitation.

Rules enforced here (per ARCHITECTURE.md §14.11.1 and API_CONTRACT.md §3.2):
- Backend creates DocumentCitation; agents only copy already-canonical citations.
- LLM must NOT calculate clinical values; this module uses deterministic parsing only.
- Low-confidence OCR (< threshold) → verification_status = "needs_verification".
- entered-in-error records are excluded by the ingestion layer before calling here.
- Each evidence item carries exactly the evidence from the page/block it came from.
- Prompt injection text in PDFs is treated as opaque content, not as an instruction.
"""

from __future__ import annotations

import uuid
from typing import Any

from src.clinical.pdf_extractor import (
    OCR_CONFIDENCE_THRESHOLD,
    BlockExtraction,
    DocumentExtraction,
)
from src.clinical.structured_fact import StructuredFact

CANONICALIZER_VERSION = "pdf-canonicalizer@1.0.0"

# Maximum snippet length returned to callers (API_CONTRACT.md: only minimal needed)
_SNIPPET_MAX = 200


def _make_snippet(text: str) -> str:
    text = text.strip()
    if len(text) <= _SNIPPET_MAX:
        return text
    return text[:_SNIPPET_MAX] + "…"


def _citation_id(document_id: str, page_number: int, block_index: int) -> str:
    return f"cit_{document_id}_p{page_number}_b{block_index}"


def _evidence_id(document_id: str, page_number: int, block_index: int) -> str:
    # Stable, deterministic ID so idempotent re-ingestion produces same IDs
    raw = f"{document_id}:p{page_number}:b{block_index}"
    return f"pdfev_{uuid.uuid5(uuid.NAMESPACE_URL, raw).hex[:12]}"


def canonicalize_extraction(
    extraction: DocumentExtraction,
    *,
    patient_id: str,
    tenant_id: str,
    document_name: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert a DocumentExtraction into canonical evidence items + verification items.

    Returns:
        (evidence_items, verification_items)

        evidence_items: list of dicts matching EvidenceItem schema for EvidencePacket
        verification_items: list of dicts for VerificationItem (low-confidence OCR)

    Each evidence item has:
        evidence_id, fact_type, normalized_value, source_value, source_time,
        verification_status, citations, patient_id, tenant_id

    The citations list on each item contains exactly one DocumentCitation dict.
    """
    evidence_items: list[dict[str, Any]] = []
    verification_items: list[dict[str, Any]] = []

    for page in extraction.pages:
        for block_index, block in enumerate(page.blocks):
            if not block.text.strip():
                continue

            citation = _build_citation(
                extraction=extraction,
                block=block,
                block_index=block_index,
                document_name=document_name,
            )

            verification_status: str
            needs_ver = False

            if block.source_type == "ocr" and block.ocr_confidence is not None:
                if block.ocr_confidence < OCR_CONFIDENCE_THRESHOLD:
                    verification_status = "needs_verification"
                    needs_ver = True
                else:
                    verification_status = "verified"
            else:
                # text_layer extraction is always verified
                verification_status = "verified"

            ev_id = _evidence_id(
                extraction.document_id, block.page_number, block_index
            )
            snippet = _make_snippet(block.text)

            # 1. Validate through StructuredFact
            fact = StructuredFact(
                fact_id=ev_id,
                patient_id=patient_id,
                # Extraction yields unstructured document text, not a parsed
                # diagnosis/lab/medication fact. Keep it on narrative routes.
                fact_type="clinical_note",
                value={
                    "raw_text": block.text,
                    "page_number": block.page_number,
                    "source_type": block.source_type,
                },
                source_document_id=extraction.document_id,
                page=block.page_number,
                evidence_text=snippet,
                confidence=block.ocr_confidence,
                verification_status=verification_status,
            )

            # 2. Convert to backward-compatible EvidenceItem dict with injected scope
            evidence_item: dict[str, Any] = {
                "evidence_id": fact.fact_id,
                "patient_id": patient_id,
                "tenant_id": tenant_id,
                "fact_type": fact.fact_type,
                "normalized_value": {
                    "statement": snippet,
                    "section_code": "changes_to_review",
                    "page_number": block.page_number,
                    "document_id": extraction.document_id,
                    "document_name": document_name,
                },
                "source_value": fact.value,
                "source_time": None,
                "verification_status": fact.verification_status,
                "citations": [citation],
                "record_status": None,
            }
            evidence_items.append(evidence_item)

            if needs_ver:
                ver_item = _build_verification_item(
                    extraction=extraction,
                    block=block,
                    block_index=block_index,
                    citation_id=citation["citation_id"],
                )
                verification_items.append(ver_item)

    return evidence_items, verification_items


def _build_citation(
    extraction: DocumentExtraction,
    block: BlockExtraction,
    block_index: int,
    document_name: str,
) -> dict[str, Any]:
    cit_id = _citation_id(extraction.document_id, block.page_number, block_index)
    snippet = _make_snippet(block.text)
    bbox_raw = block.bbox
    bbox: list[float] | None = list(bbox_raw) if bbox_raw is not None else None

    return {
        "citation_id": cit_id,
        "source_type": "pdf",
        "document_id": extraction.document_id,
        "document_name": document_name,
        "page_number": block.page_number,
        "block_id": block.block_id,
        "table_id": None,
        "bbox": bbox,
        "char_start": block.char_start,
        "char_end": block.char_end,
        "snippet": snippet,
        "source_checksum": extraction.source_checksum,
        "extraction_version": extraction.extraction_version,
        "ocr_confidence": block.ocr_confidence,
    }


def _build_verification_item(
    extraction: DocumentExtraction,
    block: BlockExtraction,
    block_index: int,
    citation_id: str,
) -> dict[str, Any]:
    ver_id = f"ver_{extraction.document_id}_p{block.page_number}_b{block_index}"
    bbox_raw = block.bbox
    bbox: list[float] | None = list(bbox_raw) if bbox_raw is not None else None
    return {
        "verification_item_id": ver_id,
        "document_id": extraction.document_id,
        "citation_id": citation_id,
        "page_number": block.page_number,
        "block_id": block.block_id,
        "bbox": bbox,
        "extracted_text": block.text,
        "corrected_text": None,
        "confidence": block.ocr_confidence,
        "status": "pending",
        "engine": block.ocr_engine,
        "engine_version": block.ocr_engine_version,
    }
