"""Ingestion service managing document raw payloads, checksums, and ingestion batches."""

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field


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
    source_checksum: str
    received_at: str
    completed_at: str | None = None
    data_watermark: str | None = None
    counts: IngestionCounts = Field(default_factory=IngestionCounts)
    errors: list[IngestionErrorDetail] = Field(default_factory=list)


class IngestionService:
    """Handles raw data ingestion, checksum calculation, and batch state."""

    def __init__(self):
        self._batches: dict[str, IngestionBatch] = {}

    def compute_checksum(self, content: bytes) -> str:
        return f"sha256:{hashlib.sha256(content).hexdigest()}"

    def create_batch(
        self,
        content: bytes,
        filename: str,
        detected_format: str = "pdf",
        patient_id: str | None = None,
    ) -> IngestionBatch:
        batch_id = f"ing_{uuid.uuid4().hex[:8]}"
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        checksum = self.compute_checksum(content)
        now_str = datetime.now().isoformat()

        batch = IngestionBatch(
            batch_id=batch_id,
            status="received",
            format=detected_format,
            source_document_id=doc_id,
            source_checksum=checksum,
            received_at=now_str,
            counts=IngestionCounts(accepted=1, quarantined=0, needs_verification=0),
            errors=[],
        )
        self._batches[batch_id] = batch
        return batch

    def get_batch(self, batch_id: str) -> IngestionBatch | None:
        return self._batches.get(batch_id)

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

        batch.status = "completed_with_warnings" if (quarantined > 0 or needs_verification > 0) else "completed"
        batch.completed_at = datetime.now().isoformat()
        batch.data_watermark = watermark
        batch.counts.accepted = accepted
        batch.counts.quarantined = quarantined
        batch.counts.needs_verification = needs_verification
        if errors:
            batch.errors.extend(errors)
        return batch
