"""LangGraph nodes for the contract-driven Clinical Review Copilot agent."""

from __future__ import annotations

from src.agents.contracts import AgentError, AgentResult, ReviewSection
from src.agents.evidence import EvidenceScopeError, build_scoped_evidence, retrieve_evidence
from src.agents.generation import compose_atomic_claims
from src.agents.policy import classify_request
from src.agents.state import ClinicalReviewState
from src.agents.verification import verify_claims

_NOT_FOUND = "Không tìm thấy thông tin này trong dữ liệu được cung cấp."
_NOT_ALLOWED = "Yêu cầu này nằm ngoài phạm vi rà soát hồ sơ được phép."
_SECTION_TITLES = {
    "patient_overview": "Tổng quan bệnh nhân",
    "active_conditions": "Tình trạng đang theo dõi",
    "current_medications": "Thuốc hiện tại",
    "recent_results": "Kết quả gần đây",
    "changes_to_review": "Thay đổi cần rà soát",
    "data_gaps": "Khoảng trống dữ liệu",
}


def validate_scope_node(state: ClinicalReviewState) -> dict:
    request = state["request"]
    runtime_scope = state["runtime_scope"]
    if (
        runtime_scope["tenant_id"] != request.tenant_id
        or runtime_scope["patient_id"] != request.patient_id
        or runtime_scope["request_id"] != request.request_id
    ):
        return {
            "status": "error",
            "errors": [AgentError(code="SCOPE_MISMATCH", message="Locked request scope mismatch.")],
        }
    try:
        packet = build_scoped_evidence(request)
    except (EvidenceScopeError, ValueError, TypeError):
        return {
            "status": "error",
            "errors": [
                AgentError(
                    code="EVIDENCE_SCOPE_INVALID",
                    message="Evidence packet failed patient or tenant scope validation.",
                )
            ],
        }
    return {"status": "running", "errors": [], "evidence_packet": packet}


def classify_question_node(state: ClinicalReviewState) -> dict:
    return {"question_type": classify_request(state["request"])}


def retrieve_evidence_node(state: ClinicalReviewState) -> dict:
    request = state["request"]
    retrieved = retrieve_evidence(
        state.get("evidence_packet", []),
        route=state["question_type"],
        question=request.question if request.task_type == "ask_chart" else None,
    )
    return {"retrieved_evidence": retrieved}


def generate_grounded_node(state: ClinicalReviewState) -> dict:
    """Route to OpenAI or deterministic generation based on backend setting.

    Treatment/prescription questions must be classified as not_allowed BEFORE
    this node runs (handled by classify_question_node + policy). This node
    only generates claims for allowed requests.

    OpenAI path:
    - Sends ONLY bounded retrieved evidence (not full patient record).
    - Falls back to deterministic if key missing / error / bad schema.
    - All output runs through the existing verifier.
    """
    import os  # noqa: PLC0415
    from src.agents.generation import compose_atomic_claims_openai  # noqa: PLC0415
    from src.agents.openai_client import build_openai_client  # noqa: PLC0415

    retrieved = state.get("retrieved_evidence", [])
    request = state["request"]

    backend = os.environ.get("AGENT_GENERATION_BACKEND", "deterministic").lower()
    api_key = os.environ.get("OPENAI_API_KEY", "")

    if backend == "openai" and api_key:
        openai_client = build_openai_client(api_key=api_key, model_name=os.environ.get("MODEL_NAME", "gpt-4o-mini"))
        proposed = compose_atomic_claims_openai(
            retrieved,
            openai_client,
            question=request.question if request.task_type == "ask_chart" else None,
        )
    else:
        proposed = compose_atomic_claims(retrieved)

    return {"proposed_claims": proposed}


def verify_claims_node(state: ClinicalReviewState) -> dict:
    claims, verification_results = verify_claims(
        state.get("proposed_claims", []),
        state.get("retrieved_evidence", []),
    )
    if any(claim.status == "needs_verification" for claim in claims):
        status = "conflicting"
    elif claims:
        status = "answered"
    else:
        status = "not_found"
    return {
        "claims": claims,
        "verification_results": verification_results,
        "status": status,
    }


def abstain_node(state: ClinicalReviewState) -> dict:
    status = state.get("status")
    if status == "error":
        return {}
    if state.get("question_type") == "not_allowed":
        return {"status": "not_allowed", "claims": [], "verification_results": []}
    return {"status": "not_found", "claims": state.get("claims", [])}


def _deduplicate_citations(claims):
    citations = []
    seen: set[str] = set()
    for claim in claims:
        for citation in claim.citations:
            if citation.citation_id not in seen:
                seen.add(citation.citation_id)
                citations.append(citation)
    return citations


def finalize_response_node(state: ClinicalReviewState) -> dict:
    request = state["request"]
    claims = state.get("claims", [])
    status = state.get("status", "error")
    citations = _deduplicate_citations(claims)
    answer = None
    sections = None
    if request.task_type == "ask_chart":
        if status in {"answered", "conflicting"}:
            answer = " ".join(claim.text for claim in claims)
            if status == "conflicting":
                answer = f"{answer} Cần xác minh các nguồn mâu thuẫn hoặc độ tin cậy thấp.".strip()
        elif status == "not_allowed":
            answer = _NOT_ALLOWED
        elif status == "not_found":
            answer = _NOT_FOUND
    else:
        section_by_claim = {proposed.claim_id: proposed.section_code for proposed in state.get("proposed_claims", [])}
        sections = []
        for section_code, title in _SECTION_TITLES.items():
            section_claims = [claim for claim in claims if section_by_claim.get(claim.claim_id) == section_code]
            if section_claims:
                sections.append(
                    ReviewSection(
                        section_code=section_code,
                        title=title,
                        claims=section_claims,
                        clinician_text=None,
                    )
                )
    confidence = None
    if status == "answered":
        confidence = "high"
    elif status == "conflicting":
        confidence = "low"
    result = AgentResult(
        task_type=request.task_type,
        status=status,
        data_watermark=request.data_watermark,
        sections=sections,
        answer=answer,
        confidence=confidence,
        claims=claims,
        citations=citations,
        errors=state.get("errors", []),
    )
    return {"public_response": result}
