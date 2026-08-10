"""Data Ingestion REST endpoints adhering strictly to API_CONTRACT.md section 4.4."""

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from src.api.dependencies import get_demo_repository
from src.clinical.demo_repository import DemoRepository
from src.clinical.ingestion import IngestionBatch, IngestionService

router = APIRouter(tags=["ingestion"])

_ingestion_service = IngestionService()


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
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB
        raise HTTPException(
            status_code=413,
            detail={"code": "FILE_TOO_LARGE", "message": "Dung lượng file vượt quá giới hạn 50MB."},
        )

    detected_format = "pdf" if file.filename and file.filename.lower().endswith(".pdf") else "fhir_r4"
    batch = _ingestion_service.create_batch(content, file.filename or "uploaded_doc", detected_format, patient_id)

    target_pid = patient_id or "PAT-001"
    wm = repo.update_watermark(target_pid)
    _ingestion_service.mark_completed(batch.batch_id, watermark=wm, accepted=1)

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
