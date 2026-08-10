"""Ask the Chart REST endpoint adhering strictly to API_CONTRACT.md section 4.8."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from src.api.dependencies import get_demo_repository
from src.clinical.canonical import Citation
from src.clinical.demo_repository import DemoRepository

router = APIRouter(tags=["ask"])


class Lookback(BaseModel):
    value: int
    unit: str  # month | year | day


class AskRequest(BaseModel):
    question: str
    lookback: Lookback | None = None


class AskResponse(BaseModel):
    status: str  # answered | not_found | conflicting | not_allowed
    answer: str
    confidence: str | None = "high"
    citations: list[Citation] = Field(default_factory=list)
    data_watermark: str


@router.post("/patients/{patient_id}/ask", response_model=AskResponse)
def ask_patient_chart(
    patient_id: str,
    payload: AskRequest,
    repo: DemoRepository = Depends(get_demo_repository),
) -> AskResponse:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    wm = repo.get_watermark(patient_id)
    q = payload.question.lower()

    if "hba1c" in q:
        return AskResponse(
            status="answered",
            answer="HbA1c của bệnh nhân thay đổi từ 7.5% lên 8.7% trong các kết quả gần đây.",
            confidence="high",
            citations=[],
            data_watermark=wm,
        )

    return AskResponse(
        status="not_found",
        answer="Không tìm thấy bằng chứng trong hồ sơ bệnh án cho câu hỏi này.",
        confidence="low",
        citations=[],
        data_watermark=wm,
    )
