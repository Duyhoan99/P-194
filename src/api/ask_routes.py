"""Ask the Chart REST endpoint adhering strictly to API_CONTRACT.md section 4.8."""

from uuid import uuid4
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from src.agents.adapter import AgentRequestAdapter
from src.agents.graph import run_agent
from src.api.auth_routes import DEFAULT_CLINICIAN
from src.api.dependencies import get_demo_repository
from src.clinical.canonical import Citation
from src.clinical.demo_repository import DemoRepository

router = APIRouter(tags=["ask"])


class Lookback(BaseModel):
    value: int
    unit: Literal["day", "month", "year"]


class AskRequest(BaseModel):
    question: str
    lookback: Lookback | None = None


class AskResponse(BaseModel):
    status: Literal["answered", "not_found", "conflicting", "not_allowed"]
    answer: str
    confidence: Literal["high", "medium", "low"] | None = "high"
    citations: list[Citation] = Field(default_factory=list)
    data_watermark: str


@router.post("/patients/{patient_id}/ask", response_model=AskResponse)
def ask_patient_chart(
    patient_id: str,
    payload: AskRequest,
    request: Request,
    response: Response,
    repo: DemoRepository = Depends(get_demo_repository),
) -> AskResponse:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
    packet = repo.build_evidence_packet(patient_id)
    memory = repo.get_patient_memory(patient_id)
    agent_request = AgentRequestAdapter().from_evidence_packet(
        packet,
        request_id=request_id,
        task_type="ask_chart",
        tenant_id=DEFAULT_CLINICIAN.tenant_id,
        user_id=DEFAULT_CLINICIAN.user_id,
        profile_versions=[],
        approved_memory=memory.model_dump(mode="json") if memory else None,
        question=payload.question,
    )
    agent_result = run_agent(
        agent_request,
        runtime_scope={
            "tenant_id": agent_request.tenant_id,
            "patient_id": patient_id,
            "request_id": request_id,
        },
    )
    if agent_result.status == "error" or agent_result.answer is None:
        trace_id = next((e.trace_id for e in agent_result.errors if getattr(e, "trace_id", None)), None)
        detail = {"code": "AGENT_UNAVAILABLE", "message": "Không thể trả lời an toàn từ dữ liệu hiện tại."}
        if trace_id:
            detail["trace_id"] = trace_id
            
        raise HTTPException(
            status_code=503,
            detail=detail,
        )
    response.headers["X-Request-ID"] = request_id
    return AskResponse(
        status=agent_result.status,
        answer=agent_result.answer,
        confidence=agent_result.confidence,
        citations=[citation.model_dump(mode="json") for citation in agent_result.citations],
        data_watermark=agent_result.data_watermark,
    )
