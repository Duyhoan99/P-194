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
from src.clinical.ai_document_parser import parse_clinical_markdown
from src.clinical.demo_repository import DemoRepository
from src.clinical.fhir_canonicalizer import canonicalize_fhir_bundle
from src.clinical.ingestion import (
    IngestionBatch,
    IngestionErrorDetail,
    IngestionService,
    ValidationError,
)
from src.clinical.pdf_canonicalizer import canonicalize_extraction
from src.clinical.pdf_extractor import (
    GeminiOcrExtractor,
    TextLayerExtractor,
    UniversalVisionExtractor,
    detect_has_text_layer,
)
from src.config import get_settings

router = APIRouter(tags=["ingestion"])

_ingestion_service = IngestionService()
_text_layer_extractor = TextLayerExtractor()


def _get_vision_extractor() -> UniversalVisionExtractor:
    settings = get_settings()
    return UniversalVisionExtractor(
        api_key=settings.llm_api_key,
        model_name=settings.llm_model_name,
        base_url=settings.llm_base_url or None,
    )


class ProcessPatientRequest(BaseModel):
    profile_versions: list[str] = Field(default_factory=lambda: ["type_2_diabetes@1.0.0"])


class ProcessPatientResponse(BaseModel):
    process_id: str
    status: str
    patient_id: str
    data_watermark: str


class QuotaResponse(BaseModel):
    used_bytes: int
    total_bytes: int


@router.post("/ingestions", response_model=IngestionBatch, status_code=status.HTTP_202_ACCEPTED)
async def ingest_file(
    file: UploadFile = File(...),
    patient_id: str | None = Form(default=None),
    new_patient_name: str | None = Form(default=None),
    format: str = Form(default="auto"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    repo: DemoRepository = Depends(get_demo_repository),
) -> IngestionBatch:
    """Ingest a PDF, Image, or JSON document for a patient.

    If patient_id is not provided, AI will parse the document to match an existing patient,
    or automatically create a new patient with extracted demographic data.
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
    # 2. Extract text / OCR / Markdown
    # ------------------------------------------------------------------
    is_json = (client_filename or "").lower().endswith(".json") or "json" in (content_type or "").lower()
    detected_format = "fhir_r4" if is_json else "pdf"
    import uuid
    temp_doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    extraction = None
    parsed_doc = None
    full_markdown = ""

    if not is_json:
        try:
            vision_extractor = _get_vision_extractor()
            extraction = vision_extractor.extract(content, temp_doc_id)
            full_markdown = "\n\n".join(p.full_text for p in extraction.pages if p.full_text)
            parsed_doc = parse_clinical_markdown(full_markdown)
        except Exception as exc:
            pass

    # ------------------------------------------------------------------
    # 3. Smart Patient Scope Resolution
    # ------------------------------------------------------------------
    target_pid = None
    if patient_id and patient_id.strip():
        # User explicitly passed patient_id
        exact_match = repo.get_patient(patient_id.strip())
        if exact_match:
            target_pid = exact_match.patient_id
        else:
            alt_match = repo.find_patient_by_identifier_or_name(patient_id.strip(), patient_id.strip())
            if alt_match:
                target_pid = alt_match.patient_id
            else:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "PATIENT_SCOPE_DENIED", "message": f"Bệnh nhân {patient_id} không tồn tại."},
                )
    else:
        # Check if new_patient_name matches an existing patient in repository
        matched_patient = None
        if new_patient_name and new_patient_name.strip():
            matched_patient = repo.find_patient_by_identifier_or_name(
                identifier=new_patient_name.strip(),
                name=new_patient_name.strip(),
            )

        # If not matched by name input, check from AI parsed_doc
        if not matched_patient and parsed_doc:
            matched_patient = repo.find_patient_by_identifier_or_name(
                identifier=parsed_doc.patient_id,
                name=parsed_doc.patient_name,
            )

        if matched_patient:
            target_pid = matched_patient.patient_id
        else:
            # Check if parsed_doc has a specific patient_id that doesn't exist yet
            doc_pid = parsed_doc.patient_id if (parsed_doc and parsed_doc.patient_id) else None
            target_pid = doc_pid if (doc_pid and not repo.get_patient(doc_pid)) else f"PAT-NEW-{uuid.uuid4().hex[:6].upper()}"
            extracted_name = parsed_doc.patient_name if (parsed_doc and parsed_doc.patient_name) else None
            name = new_patient_name.strip() if (new_patient_name and new_patient_name.strip()) else (extracted_name or f"Bệnh nhân mới {target_pid[-4:]}")
            repo.create_blank_patient(target_pid, name)


    # ------------------------------------------------------------------
    # 4. Create Batch in Document Store
    # ------------------------------------------------------------------
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
    # 5. Process JSON / PDF canonicalization & Clinical Entity Ingestion
    # ------------------------------------------------------------------
    if is_json:
        try:
            import json
            evidence_items = canonicalize_fhir_bundle(
                json.loads(content), patient_id=target_pid, tenant_id="ten_demo",
                document_id=stored_doc.document_id, source_checksum=stored_doc.checksum,
            )
            verification_items = []
            _ingestion_service.document_store.mark_extracted(
                stored_doc.document_id,
                {"resource_count": len(evidence_items), "is_fhir": True},
            )
        except Exception as exc:
            return _ingestion_service.mark_failed(
                batch.batch_id,
                errors=[IngestionErrorDetail(code="FHIR_VALIDATION_FAILED", message=str(exc)[:200])],
            )
    else:
        if extraction is None or not extraction.pages:
            try:
                vision_extractor = _get_vision_extractor()
                extraction = vision_extractor.extract(content, stored_doc.document_id)
                full_markdown = "\n\n".join(p.full_text for p in extraction.pages if p.full_text)
                if not parsed_doc:
                    parsed_doc = parse_clinical_markdown(full_markdown)
            except Exception as exc:
                batch = _ingestion_service.mark_failed(
                    batch.batch_id,
                    errors=[IngestionErrorDetail(code="EXTRACTION_FAILED", message=str(exc)[:200])],
                )
                return batch

        _ingestion_service.document_store.mark_extracted(
            stored_doc.document_id,
            {
                "page_count": extraction.page_count,
                "has_text_layer": extraction.has_text_layer,
                "markdown": full_markdown,
            },
        )

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
    # 6. Add evidence & structured clinical data to repository
    # ------------------------------------------------------------------
    try:
        if is_json:
            repo.add_fhir_evidence(target_pid, evidence_items)
        else:
            # 1. Add canonical PDF evidence for citations & AI copilot
            repo.add_pdf_evidence(
                patient_id=target_pid,
                document_id=stored_doc.document_id,
                evidence_items=evidence_items,
                verification_items=verification_items if verification_items else None,
            )
            # 2. Add parsed clinical entities (Observations, Encounters, Conditions) to patient trends & timeline
            if parsed_doc:
                repo.add_parsed_clinical_document(
                    patient_id=target_pid,
                    parsed_doc=parsed_doc,
                    document_id=stored_doc.document_id,
                    document_name=stored_doc.document_name,
                )

            from src.agents.retrieval.vector import index_evidence
            index_evidence(tenant_id="ten_demo", patient_id=target_pid, items=evidence_items)

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

    no_evidence = not evidence_items
    completion_errors = (
        [IngestionErrorDetail(code="NO_EVIDENCE_EXTRACTED", message="Document produced no usable evidence.")]
        if no_evidence else None
    )
    batch = _ingestion_service.mark_completed(
        batch.batch_id,
        watermark=wm,
        accepted=max(accepted_count, 0),
        quarantined=1 if no_evidence else 0,
        needs_verification=needs_ver_count,
        errors=completion_errors,
    )
    return batch


@router.get("/ingestions", response_model=list[IngestionBatch])
def list_ingestions(limit: int = 10) -> list[IngestionBatch]:
    """List recent ingestion batches."""
    return _ingestion_service.list_recent_batches(limit)


@router.get("/ingestions/quota", response_model=QuotaResponse)
def get_quota() -> QuotaResponse:
    """Get storage quota usage."""
    stats = _ingestion_service.get_storage_stats()
    return QuotaResponse(
        used_bytes=stats["used_bytes"],
        total_bytes=stats["total_bytes"],
    )


@router.get("/ingestions/{batch_id}", response_model=IngestionBatch)
def get_ingestion_status(batch_id: str) -> IngestionBatch:
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
