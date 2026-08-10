"""Patient REST endpoints adhering strictly to API_CONTRACT.md sections 4.3, 4.6, 4.11."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from src.api.dependencies import get_demo_repository
from src.clinical.canonical import (
    PatientSummary,
    TimelineEvent,
    TrendPoint,
    DrugInteractionFlag,
    PatientMemory,
)
from src.clinical.demo_repository import DemoRepository

router = APIRouter(tags=["patients"])


class PatientListResponse(BaseModel):
    items: list[PatientSummary]
    page: int
    page_size: int
    total: int


class TimelineResponse(BaseModel):
    items: list[TimelineEvent]
    data_watermark: str
    page: int
    page_size: int
    total: int


class TrendResponse(BaseModel):
    code: str
    display: str
    unit: str
    points: list[TrendPoint]
    profile_version: str = "type_2_diabetes@1.0.0"
    data_watermark: str


class DrugInteractionListResponse(BaseModel):
    items: list[DrugInteractionFlag]
    data_watermark: str


@router.get("/patients", response_model=PatientListResponse)
def list_patients(
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repo: DemoRepository = Depends(get_demo_repository),
) -> PatientListResponse:
    items, total = repo.list_patients(search, page, page_size)
    return PatientListResponse(items=items, page=page, page_size=page_size, total=total)


@router.get("/patients/{patient_id}/timeline", response_model=TimelineResponse)
def get_timeline(
    patient_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repo: DemoRepository = Depends(get_demo_repository),
) -> TimelineResponse:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    events = repo.get_timeline(patient_id)
    total = len(events)
    start = (page - 1) * page_size
    paged = events[start:start + page_size]
    wm = repo.get_watermark(patient_id)

    return TimelineResponse(
        items=paged,
        data_watermark=wm,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/patients/{patient_id}/trends", response_model=TrendResponse)
def get_trends(
    patient_id: str,
    code: str = Query(..., description="Mã LOINC xét nghiệm"),
    repo: DemoRepository = Depends(get_demo_repository),
) -> TrendResponse:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    display, unit, points = repo.get_trends(patient_id, code)
    wm = repo.get_watermark(patient_id)

    return TrendResponse(
        code=code,
        display=display,
        unit=unit,
        points=points,
        profile_version="type_2_diabetes@1.0.0",
        data_watermark=wm,
    )


@router.get("/patients/{patient_id}/drug-interactions", response_model=DrugInteractionListResponse)
def get_drug_interactions(
    patient_id: str,
    repo: DemoRepository = Depends(get_demo_repository),
) -> DrugInteractionListResponse:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    wm = repo.get_watermark(patient_id)
    return DrugInteractionListResponse(items=[], data_watermark=wm)


@router.get("/patients/{patient_id}/memory", response_model=PatientMemory)
def get_patient_memory(
    patient_id: str,
    version: int | None = None,
    repo: DemoRepository = Depends(get_demo_repository),
) -> PatientMemory:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    memory = repo.get_patient_memory(patient_id, version)
    if not memory:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "Chưa có bộ nhớ bệnh nhân được duyệt."},
        )
    return memory
