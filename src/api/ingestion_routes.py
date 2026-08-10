"""Data Ingestion REST endpoints adhering strictly to API_CONTRACT.md section 4.4.

Security rules:
- Client filename is NEVER used for file storage paths.
- Path traversal is blocked at the ingestion layer.
- Validation (size/MIME/signature/idempotency) before any processing.
- Watermark is bumped ONLY after successful extraction and evidence addition.
- On any extraction failure, batch is marked 'failed'; watermark is NOT changed.
- Agents never touch source files; they only receive EvidencePacket.
"""

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from src.api.dependencies import get_demo_repository
from src.clinical.demo_repository import DemoRepository
from src.clinical.ingestion import (
    IngestionBatch,
    IngestionErrorDetail,
    IngestionService,
    ValidationError,
)
from src.clinical.pdf_canonicalizer import canonicalize_extraction
from src.clinical.pdf_extractor import (
    MockOcrExtractor,
    TextLayerExtractor,
    detect_has_text_layer,
)

router = APIRouter(tags=["ingestion"])

_ingestion_service = IngestionService()

# Use TextLayerExtractor by default; tests can inject MockOcrExtractor
_text_layer_extractor = TextLayerExtractor()
_mock_ocr_extractor = MockOcrExtractor(page_count=1)


class ProcessPatientRequest(BaseModel):
    profile_versions: list[str] = Field(default_factory=lambda: ["type_2_diabetes@1.0.0"])


class ProcessPatientResponse(BaseModel):
    process_id: str
    status: str
    patient_id: str
    data_watermark: str


@router.post("/ingestions", response_model=IngestionBatch, status_code=status.HTTP_202_ACCEPTED)
async def ingest_file(
    file: UploadFile = File(...),
    patient_id: str | None = Form(default=None),
    format: str = Form(default="auto"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    repo: DemoRepository = Depends(get_demo_repository),
) -> IngestionBatch:
    """Ingest a PDF document for a patient.

    Pipeline:
    1. Read content.
    2. Validate (size, MIME, signature, idempotency).
    3. Create batch + store document (server-generated document_id).
    4. Extract text (text layer) or OCR (abstraction).
    5. Canonicalize → EvidenceItems with DocumentCitation.
    6. Add PDF evidence to repository (patient-scoped).
    7. Mark reviews stale (new data).
    8. Update watermark ONLY on success.
    9. Mark batch completed/completed_with_warnings.
    """
    content = await file.read()
    client_filename = file.filename
    content_type = file.content_type

    # ------------------------------------------------------------------
    # 1. Validate upload
    # ------------------------------------------------------------------
    try:
        _ingestion_service.validate_upload(
            content=content,
            client_filename=client_filename,
            content_type=content_type,
            idempotency_key=idempotency_key,
        )
    except ValidationError as e:
        http_status = {
            "FILE_TOO_LARGE": 413,
            "UNSUPPORTED_FORMAT": 415,
            "DUPLICATE_REQUEST": 409,
        }.get(e.code, 422)
        raise HTTPException(
            status_code=http_status,
            detail={"code": e.code, "message": e.message},
        )

    # ------------------------------------------------------------------
    # 2. Patient scope check
    # ------------------------------------------------------------------
    target_pid = patient_id or "PAT-001"
    if not repo.get_patient(target_pid):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại."},
        )

    # ------------------------------------------------------------------
    # 3. Determine format and create batch
    # ------------------------------------------------------------------
    detected_format = "pdf" if (client_filename or "").lower().endswith(".pdf") else format

    batch, stored_doc = _ingestion_service.create_batch(
        content=content,
        client_filename=client_filename,
        detected_format=detected_format,
        patient_id=target_pid,
        idempotency_key=idempotency_key,
    )

    # If idempotency key matched same content, batch is already completed
    if batch.status in {"completed", "completed_with_warnings"}:
        return batch

    # Mark as processing
    _ingestion_service.mark_processing(batch.batch_id)

    # ------------------------------------------------------------------
    # 4. Extract text / OCR
    # ------------------------------------------------------------------
    try:
        # Use text layer extractor for PDFs with a text layer
        if detect_has_text_layer(content):
            extraction = _text_layer_extractor.extract(content, stored_doc.document_id)
        else:
            # For scan/image PDFs use mock OCR (real OCR engine would be injected here)
            extraction = _mock_ocr_extractor.extract(content, stored_doc.document_id)

        _ingestion_service.document_store.mark_extracted(
            stored_doc.document_id,
            {"page_count": extraction.page_count, "has_text_layer": extraction.has_text_layer},
        )

    except Exception as exc:
        batch = _ingestion_service.mark_failed(
            batch.batch_id,
            errors=[IngestionErrorDetail(code="EXTRACTION_FAILED", message=str(exc)[:200])],
        )
        return batch

    # ------------------------------------------------------------------
    # 5. Canonicalize extraction → EvidenceItems + VerificationItems
    # ------------------------------------------------------------------
    try:
        display_name = stored_doc.document_name
        evidence_items, verification_items = canonicalize_extraction(
            extraction,
            patient_id=target_pid,
            tenant_id="ten_demo",
            document_name=display_name,
        )
    except Exception as exc:
        batch = _ingestion_service.mark_failed(
            batch.batch_id,
            errors=[IngestionErrorDetail(code="CANONICALIZATION_FAILED", message=str(exc)[:200])],
        )
        return batch

    # ------------------------------------------------------------------
    # 6. Add PDF evidence to repository (patient-scoped)
    # ------------------------------------------------------------------
    try:
        repo.add_pdf_evidence(
            patient_id=target_pid,
            document_id=stored_doc.document_id,
            evidence_items=evidence_items,
            verification_items=verification_items if verification_items else None,
        )
    except Exception as exc:
        batch = _ingestion_service.mark_failed(
            batch.batch_id,
            errors=[IngestionErrorDetail(code="REPOSITORY_ERROR", message=str(exc)[:200])],
        )
        return batch

    # ------------------------------------------------------------------
    # 7. Mark existing reviews stale (new data arrived)
    # ------------------------------------------------------------------
    repo.mark_reviews_stale(target_pid)

    # ------------------------------------------------------------------
    # 8. Update watermark ONLY after successful ingestion
    # ------------------------------------------------------------------
    wm = repo.update_watermark(target_pid)

    # ------------------------------------------------------------------
    # 9. Mark batch completed
    # ------------------------------------------------------------------
    needs_ver_count = sum(
        1 for item in evidence_items if item.get("verification_status") == "needs_verification"
    )
    accepted_count = len(evidence_items) - needs_ver_count

    batch = _ingestion_service.mark_completed(
        batch.batch_id,
        watermark=wm,
        accepted=max(accepted_count, 0),
        quarantined=0,
        needs_verification=needs_ver_count,
    )
    return batch


@router.get("/ingestions/{batch_id}", response_model=IngestionBatch)
def get_ingestion_batch(batch_id: str) -> IngestionBatch:
    batch = _ingestion_service.get_batch(batch_id)
    if not batch:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": f"Không tìm thấy đợt nhập dữ liệu {batch_id}."},
        )
    return batch


@router.post("/patients/{patient_id}/process", response_model=ProcessPatientResponse, status_code=status.HTTP_202_ACCEPTED)
def process_patient(
    patient_id: str,
    payload: ProcessPatientRequest,
    repo: DemoRepository = Depends(get_demo_repository),
) -> ProcessPatientResponse:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    wm = repo.get_watermark(patient_id)
    return ProcessPatientResponse(
        process_id=f"proc_{patient_id}_01",
        status="completed",
        patient_id=patient_id,
        data_watermark=wm,
    )
