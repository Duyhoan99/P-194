"""Ingestion service managing document raw payloads, checksums, and ingestion batches.

Security rules (per ARCHITECTURE.md and API_CONTRACT.md):
- Filename from client is NEVER used as a storage key or document ID.
- Path traversal is blocked by never joining client filename to any path.
- Document IDs are server-generated UUIDs.
- Idempotency key + checksum prevents duplicate ingestion.
- Only ingestion layer stores/reads raw bytes; agents never touch source files.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# Supported MIME types and file extensions for PDF uploads
_ALLOWED_MIME_TYPES = frozenset({"application/pdf", "application/x-pdf", "application/json", "image/png", "image/jpeg", "image/jpg"})
_ALLOWED_EXTENSIONS = frozenset({".pdf", ".json", ".png", ".jpg", ".jpeg"})
# PDF magic bytes signature
_PDF_MAGIC = b"%PDF-"
# Maximum file size: 50 MB
_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


class IngestionCounts(BaseModel):
    accepted: int = 0
    quarantined: int = 0
    needs_verification: int = 0


class IngestionErrorDetail(BaseModel):
    code: str
    message: str
    item_id: str | None = None


class IngestionBatch(BaseModel):
    batch_id: str
    status: str  # received, validating, processing, completed, completed_with_warnings, failed
    format: str  # pdf, fhir_r4, auto
    source_document_id: str
    patient_id: str | None = None
    source_checksum: str
    received_at: str
    completed_at: str | None = None
    data_watermark: str | None = None
    counts: IngestionCounts = Field(default_factory=IngestionCounts)
    errors: list[IngestionErrorDetail] = Field(default_factory=list)


class ValidationError(Exception):
    """Raised when an uploaded file fails validation."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class StoredDocument:
    """Metadata and content for a stored document."""

    document_id: str
    patient_id: str
    document_name: str  # sanitized display name (NOT derived from client filename for paths)
    content: bytes
    checksum: str
    format: str
    received_at: str
    extracted: bool = False
    extraction_data: dict[str, Any] = field(default_factory=dict)


class DocumentStore:
    """In-memory document storage.

    Documents are indexed by (patient_id, document_id). The client-supplied
    filename is NEVER used as a storage key — only for display purposes after
    sanitization.
    """

    def __init__(self) -> None:
        self._docs: dict[str, StoredDocument] = {}  # key = document_id
        self._patient_docs: dict[str, list[str]] = {}  # patient_id -> [doc_id, ...]
        self._idempotency: dict[str, str] = {}  # idempotency_key -> document_id

    def store(
        self,
        document_id: str,
        patient_id: str,
        document_name: str,
        content: bytes,
        checksum: str,
        format: str,
        idempotency_key: str | None = None,
    ) -> StoredDocument:
        now_str = datetime.now().isoformat()
        doc = StoredDocument(
            document_id=document_id,
            patient_id=patient_id,
            document_name=document_name,
            content=content,
            checksum=checksum,
            format=format,
            received_at=now_str,
        )
        self._docs[document_id] = doc
        self._patient_docs.setdefault(patient_id, []).append(document_id)
        if idempotency_key:
            self._idempotency[idempotency_key] = document_id
        return doc

    def get(self, document_id: str) -> StoredDocument | None:
        return self._docs.get(document_id)

    def get_by_idempotency_key(self, key: str) -> StoredDocument | None:
        doc_id = self._idempotency.get(key)
        if doc_id:
            return self._docs.get(doc_id)
        return None

    def list_for_patient(self, patient_id: str) -> list[StoredDocument]:
        ids = self._patient_docs.get(patient_id, [])
        return [self._docs[d] for d in ids if d in self._docs]

    def delete_for_patient(self, patient_id: str) -> None:
        doc_ids = self._patient_docs.pop(patient_id, [])
        for doc_id in doc_ids:
            self._docs.pop(doc_id, None)
            keys_to_remove = [k for k, v in self._idempotency.items() if v == doc_id]
            for k in keys_to_remove:
                self._idempotency.pop(k, None)

    def mark_extracted(self, document_id: str, extraction_data: dict[str, Any]) -> None:
        doc = self._docs.get(document_id)
        if doc:
            doc.extracted = True
            doc.extraction_data = extraction_data


class IngestionService:
    """Handles raw data ingestion, checksum calculation, and batch state.

    This is the ONLY layer allowed to store or read raw document bytes.
    Agents and LLMs receive only the EvidencePacket, never source files.
    """

    def __init__(self) -> None:
        self._batches: dict[str, IngestionBatch] = {}
        self.document_store = DocumentStore()

    def compute_checksum(self, content: bytes) -> str:
        return f"sha256:{hashlib.sha256(content).hexdigest()}"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_upload(
        self,
        content: bytes,
        client_filename: str | None,
        content_type: str | None,
        idempotency_key: str | None = None,
    ) -> None:
        """Validate an uploaded file. Raises ValidationError on failure.

        Security:
        - Filename from client is never used for path operations.
        - Only whitelist of MIME types and extensions allowed.
        - PDF signature checked on raw bytes.
        - File size capped.
        - Idempotency key conflict detection (same key, different content).
        """
        # 1. Size check
        if len(content) > _MAX_FILE_SIZE_BYTES:
            raise ValidationError("FILE_TOO_LARGE", "Dung lượng file vượt quá giới hạn 50MB.")

        # 2. MIME type check (informational — not trusted alone; signature is ground truth)
        if content_type and content_type.split(";")[0].strip().lower() not in _ALLOWED_MIME_TYPES:
            raise ValidationError(
                "UNSUPPORTED_FORMAT",
                f"Kiểu MIME không được hỗ trợ: {content_type}. Chỉ chấp nhận PDF và JSON.",
            )

        # 3. Extension check — only from the portion after last dot, case-insensitive
        if client_filename:
            # Extract extension safely — never join to filesystem path
            dot_idx = client_filename.rfind(".")
            ext = client_filename[dot_idx:].lower() if dot_idx != -1 else ""
            if ext not in _ALLOWED_EXTENSIONS:
                raise ValidationError(
                    "UNSUPPORTED_FORMAT",
                    f"Phần mở rộng file không được hỗ trợ: '{ext}'. Chỉ chấp nhận .pdf và .json.",
                )

        # 4. Content signature check
        is_pdf_by_ext = client_filename and client_filename.lower().endswith(".pdf")
        is_pdf_by_mime = content_type and "pdf" in content_type.lower()
        is_img_by_ext = client_filename and client_filename.lower().endswith((".png", ".jpg", ".jpeg"))
        is_img_by_mime = content_type and "image" in content_type.lower()
        
        if is_pdf_by_ext or is_pdf_by_mime:
            if not content.startswith(_PDF_MAGIC):
                raise ValidationError(
                    "UNSUPPORTED_FORMAT",
                    "File không có chữ ký PDF hợp lệ. Chỉ chấp nhận tài liệu PDF thực.",
                )
        elif is_img_by_ext or is_img_by_mime:
            # For images, we can do basic magic byte checks
            if not (content.startswith(b"\x89PNG") or content.startswith(b"\xff\xd8")):
                raise ValidationError(
                    "UNSUPPORTED_FORMAT",
                    "File ảnh không hợp lệ (chỉ hỗ trợ PNG, JPEG).",
                )
        else:
            # Basic JSON validation check
            try:
                import json
                json.loads(content)
            except json.JSONDecodeError:
                raise ValidationError(
                    "UNSUPPORTED_FORMAT",
                    "File JSON không hợp lệ.",
                )

        # 5. Idempotency: same key + different content = conflict
        if idempotency_key:
            existing = self.document_store.get_by_idempotency_key(idempotency_key)
            if existing:
                new_checksum = self.compute_checksum(content)
                if existing.checksum != new_checksum:
                    raise ValidationError(
                        "DUPLICATE_REQUEST",
                        "Khóa idempotency đã được dùng với nội dung khác.",
                    )

    # ------------------------------------------------------------------
    # Batch management
    # ------------------------------------------------------------------

    def create_batch(
        self,
        content: bytes,
        client_filename: str | None,
        detected_format: str = "pdf",
        patient_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[IngestionBatch, StoredDocument]:
        """Create a batch and store the document. Returns (batch, stored_doc).

        The document_id is server-generated and never derived from the filename.
        The display name (document_name) is sanitized from the client filename.
        """
        # Check idempotency: same key + same content = return existing batch
        if idempotency_key:
            existing_doc = self.document_store.get_by_idempotency_key(idempotency_key)
            if existing_doc:
                existing_checksum = self.compute_checksum(content)
                if existing_doc.checksum == existing_checksum:
                    # Find existing batch for this document
                    for batch in self._batches.values():
                        if batch.source_document_id == existing_doc.document_id:
                            return batch, existing_doc

        batch_id = f"ing_{uuid.uuid4().hex[:8]}"
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        checksum = self.compute_checksum(content)
        now_str = datetime.now().isoformat()

        # Sanitize display name: only keep basename, no path separators
        if client_filename:
            safe_name = client_filename.replace("\\", "/").split("/")[-1]
            # Remove any characters that could be used for injection
            safe_name = "".join(c for c in safe_name if c.isprintable() and c not in '<>:"|?*')
        else:
            safe_name = f"document_{doc_id}.pdf"

        target_pid = patient_id or "UNKNOWN"

        stored_doc = self.document_store.store(
            document_id=doc_id,
            patient_id=target_pid,
            document_name=safe_name,
            content=content,
            checksum=checksum,
            format=detected_format,
            idempotency_key=idempotency_key,
        )

        batch = IngestionBatch(
            batch_id=batch_id,
            status="received",
            format=detected_format,
            source_document_id=doc_id,
            patient_id=target_pid,
            source_checksum=checksum,
            received_at=now_str,
            counts=IngestionCounts(accepted=0, quarantined=0, needs_verification=0),
            errors=[],
        )
        self._batches[batch_id] = batch
        return batch, stored_doc

    def list_recent_batches(self, limit: int = 10) -> list[IngestionBatch]:
        """Return the most recent ingestion batches."""
        return sorted(self._batches.values(), key=lambda b: b.received_at, reverse=True)[:limit]

    def get_batch(self, batch_id: str) -> IngestionBatch | None:
        return self._batches.get(batch_id)

    def mark_processing(self, batch_id: str) -> IngestionBatch:
        batch = self._batches[batch_id]
        batch.status = "processing"
        return batch

    def mark_completed(
        self,
        batch_id: str,
        watermark: str,
        accepted: int = 1,
        quarantined: int = 0,
        needs_verification: int = 0,
        errors: list[IngestionErrorDetail] | None = None,
    ) -> IngestionBatch:
        batch = self._batches.get(batch_id)
        if not batch:
            raise KeyError(f"Batch {batch_id} not found")

        batch.status = (
            "completed_with_warnings"
            if (quarantined > 0 or needs_verification > 0)
            else "completed"
        )
        batch.completed_at = datetime.now().isoformat()
        batch.data_watermark = watermark
        batch.counts.accepted = accepted
        batch.counts.quarantined = quarantined
        batch.counts.needs_verification = needs_verification
        if errors:
            batch.errors.extend(errors)
        return batch

    def mark_failed(
        self,
        batch_id: str,
        errors: list[IngestionErrorDetail],
    ) -> IngestionBatch:
        """Mark a batch as failed. Does NOT update watermark — caller must not call
        update_watermark either if ingestion failed."""
        batch = self._batches.get(batch_id)
        if not batch:
            raise KeyError(f"Batch {batch_id} not found")
        batch.status = "failed"
        batch.completed_at = datetime.now().isoformat()
        if errors:
            batch.errors.extend(errors)
        return batch

    def get_storage_stats(self) -> dict[str, Any]:
        total_bytes = sum(len(doc.content) for doc in self.document_store._docs.values())
        return {
            "used_bytes": total_bytes,
            "total_bytes": 100 * 1024 * 1024 * 1024, # 100GB limit as hardcoded in UI
        }

    def delete_for_patient(self, patient_id: str) -> None:
        self.document_store.delete_for_patient(patient_id)
        batch_ids = [b_id for b_id, b in self._batches.items() if b.patient_id == patient_id]
        for b_id in batch_ids:
            self._batches.pop(b_id, None)
