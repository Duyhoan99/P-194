"""Ask the Chart REST endpoint adhering strictly to API_CONTRACT.md section 4.8."""

from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from src.agents.adapter import AgentRequestAdapter
from src.agents.graph import clinical_agent, run_agent
from src.api.auth_routes import DEFAULT_CLINICIAN
from src.api.dependencies import get_demo_repository
from src.api.session_manager import ChatSession, session_manager
from src.clinical.canonical import Citation
from src.clinical.care_plan_agent import CarePlanResponse, care_plan_agent
from src.clinical.demo_repository import DemoRepository

router = APIRouter(tags=["ask"])


_CARE_PLAN_MARKERS = (
    "kế hoạch chăm sóc",
    "chăm sóc tại nhà",
    "hướng dẫn tại nhà",
    "phiếu hướng dẫn điều trị",
    "phác đồ gợi ý",
    "gợi ý phác đồ",
    "care plan",
)


def _is_care_plan_question(question: str) -> bool:
    normalized = question.strip().casefold()
    return any(marker in normalized for marker in _CARE_PLAN_MARKERS)


def _care_plan_answer(care_plan: CarePlanResponse) -> str:
    plan = care_plan.plan
    lines = [
        "### Bản nháp kế hoạch chăm sóc cá nhân hóa",
        plan.doctor_greeting,
        "",
        "**Thuốc đang hoạt động trong hồ sơ**",
        f"- Lần dùng 1: {plan.morning_meds}",
        f"- Lần dùng 2: {plan.evening_meds}",
        f"- Lưu ý nguồn thuốc: {plan.medication_note}",
        "",
        "**Dinh dưỡng**",
        f"- Nên ưu tiên: {plan.diet_good}",
        f"- Cần hạn chế: {plan.diet_bad}",
        "",
        f"**Vận động và tự theo dõi:** {plan.exercise}",
        f"**Dấu hiệu cần xử trí khẩn:** {plan.emergency_warning}",
        f"**Tái khám:** {plan.follow_up}",
    ]
    if care_plan.safety_flags:
        lines.extend(["", "**Cờ an toàn cần bác sĩ rà soát**"])
        lines.extend(f"- {flag}" for flag in care_plan.safety_flags)
    lines.extend(["", f"> {care_plan.disclaimer}"])
    return "\n".join(lines)


def _care_plan_citations(approved_memory: object) -> list[dict]:
    raw = approved_memory.model_dump(mode="json") if hasattr(approved_memory, "model_dump") else {}
    citations: list[dict] = []
    seen: set[str] = set()
    for item in raw.get("items", []):
        for citation in item.get("citations", []):
            citation_id = str(citation.get("citation_id") or "")
            if citation_id and citation_id not in seen:
                seen.add(citation_id)
                citations.append(citation)
    return citations


class Lookback(BaseModel):
    value: int
    unit: Literal["day", "month", "year"]


class AskRequest(BaseModel):
    question: str
    lookback: Lookback | None = None
    session_id: str | None = None


class AskResponse(BaseModel):
    status: Literal["answered", "not_found", "conflicting", "not_allowed"]
    answer: str
    confidence: Literal["high", "medium", "low"] | None = "high"
    citations: list[Citation] = Field(default_factory=list)
    data_watermark: str


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ChatHistoryResponse(BaseModel):
    messages: list[HistoryMessage]


@router.post("/patients/{patient_id}/ask", response_model=AskResponse)
async def ask_patient_chart(
    patient_id: str,
    payload: AskRequest,
    request: Request,
    response: Response,
    repo: DemoRepository = Depends(get_demo_repository),
) -> AskResponse:
    patient = repo.get_patient(patient_id)
    if not patient:
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    if _is_care_plan_question(payload.question):
        approved_review = repo.get_review(patient_id)
        if (
            not approved_review
            or approved_review.status != "approved"
            or not approved_review.is_current_watermark
            or approved_review.data_watermark != repo.get_watermark(patient_id)
        ):
            return AskResponse(
                status="not_allowed",
                answer="Bác sĩ cần hoàn tất và ký duyệt bản tóm tắt hiện tại trước khi yêu cầu agent hỗ trợ bệnh lý tạo phác đồ.",
                confidence="high",
                citations=[],
                data_watermark=repo.get_watermark(patient_id),
            )
        approved_memory = repo.get_patient_memory(patient_id, approved_review.memory_version_used)
        if not approved_memory or approved_memory.source_review_version_id != approved_review.review_version_id:
            return AskResponse(
                status="not_allowed",
                answer="Không tìm thấy bản tóm tắt đã duyệt khớp với phiên bản hiện tại.",
                confidence="high",
                citations=[],
                data_watermark=approved_review.data_watermark,
            )
        care_plan = await care_plan_agent.generate_care_plan(
            patient=patient,
            approved_review=approved_review,
            approved_memory=approved_memory,
        )
        return AskResponse(
            status="conflicting" if care_plan.data_summary.conflicts else "answered",
            answer=_care_plan_answer(care_plan),
            confidence="low" if care_plan.status == "needs_review" else "medium",
            citations=_care_plan_citations(approved_memory),
            data_watermark=approved_review.data_watermark,
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
        session_id=payload.session_id,
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
    if payload.session_id:
        session_manager.upsert_session(payload.session_id, patient_id, payload.question)

    response.headers["X-Request-ID"] = request_id
    return AskResponse(
        status=agent_result.status,
        answer=agent_result.answer,
        confidence=agent_result.confidence,
        citations=[citation.model_dump(mode="json") for citation in agent_result.citations],
        data_watermark=agent_result.data_watermark,
    )


@router.get("/patients/{patient_id}/ask/history", response_model=ChatHistoryResponse)
def get_chat_history(
    patient_id: str,
    session_id: str,
    repo: DemoRepository = Depends(get_demo_repository),
) -> ChatHistoryResponse:
    patient = repo.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Bệnh nhân không tồn tại.")

    thread_id = f"{DEFAULT_CLINICIAN.tenant_id}:{patient_id}:{session_id}"
    try:
        state_snapshot = clinical_agent.get_state({"configurable": {"thread_id": thread_id}})
    except Exception:
        return ChatHistoryResponse(messages=[])

    if not state_snapshot or not state_snapshot.values:
        return ChatHistoryResponse(messages=[])

    messages = state_snapshot.values.get("messages", [])
    history = []

    for msg in messages:
        if isinstance(msg, tuple) and len(msg) == 2:
            role = "user" if msg[0] == "human" else "assistant"
            history.append(HistoryMessage(role=role, text=msg[1]))
        elif hasattr(msg, "type") and hasattr(msg, "content"):
            role = "user" if msg.type == "human" else "assistant"
            history.append(HistoryMessage(role=role, text=str(msg.content)))

    return ChatHistoryResponse(messages=history)


@router.get("/patients/{patient_id}/ask/sessions", response_model=list[ChatSession])
def list_chat_sessions(patient_id: str, repo: DemoRepository = Depends(get_demo_repository)):
    if not repo.get_patient(patient_id):
        raise HTTPException(status_code=404, detail="Bệnh nhân không tồn tại.")
    return session_manager.get_sessions(patient_id)


class RenameSessionRequest(BaseModel):
    title: str


@router.put("/patients/{patient_id}/ask/sessions/{session_id}")
def rename_chat_session(patient_id: str, session_id: str, req: RenameSessionRequest):
    success = session_manager.rename_session(session_id, req.title)
    if not success:
        raise HTTPException(status_code=404, detail="Session không tồn tại.")
    return {"success": True}


@router.delete("/patients/{patient_id}/ask/sessions/{session_id}")
def delete_chat_session(patient_id: str, session_id: str):
    success = session_manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session không tồn tại.")
    return {"success": True}
