"""LangGraph nodes for the contract-driven Clinical Review Copilot agent."""

from __future__ import annotations

from src.agents.contracts import AgentError, AgentResult, ReviewSection
from src.agents.evidence import EvidenceScopeError, build_scoped_evidence, retrieve_evidence
from src.agents.generation import compose_atomic_claims
from src.agents.llm_client import get_llm_runtime
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
    from src.agents.retrieval.conflict import detect_conflicts
    request = state["request"]
    
    question_type = state["question_type"]
    if isinstance(question_type, str) and question_type == "not_allowed":
        return {"retrieved_evidence": [], "conflicts": []}
        
    if isinstance(question_type, dict) and question_type.get("task_type") == "conflict_check":
        packet = state.get("evidence_packet", [])
        detected = detect_conflicts([item.item for item in packet])
        participant_ids = {
            conflict.item_a.evidence_id for conflict in detected
        } | {
            conflict.item_b.evidence_id for conflict in detected
        }
        retrieved = [item for item in packet if item.item.evidence_id in participant_ids]
        return {
            "retrieved_evidence": retrieved,
            "conflicts": [conflict.model_dump(mode="json") for conflict in detected],
        }

    retrieved = retrieve_evidence(
        state.get("evidence_packet", []),
        route=question_type,
        question=request.question if request.task_type == "ask_chart" else None,
    )
    conflicts = [c.model_dump(mode="json") for c in detect_conflicts([item.item for item in retrieved])]
    return {"retrieved_evidence": retrieved, "conflicts": conflicts}


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
    from src.agents.generation import compose_atomic_claims_llm  # noqa: PLC0415

    retrieved = state.get("retrieved_evidence", [])
    request = state["request"]

    runtime = get_llm_runtime()

    qt = state.get("question_type")
    is_conversational = isinstance(qt, dict) and (qt.get("task_type") == "conversation" or not qt.get("retrieval_required", True))

    if is_conversational:
        import re
        from src.agents.generation import ProposedClaim
        normalized_question = (request.question or "").strip().casefold()
        if isinstance(qt, dict) and qt.get("task_type") == "clarification":
            greeting_text = "Tôi chưa hiểu câu hỏi. Bạn có thể diễn đạt rõ hơn nội dung cần tra cứu không?"
            conversation_intent = "clarification"
        elif normalized_question in {"tạm biệt", "hẹn gặp lại", "bye", "goodbye"}:
            greeting_text = "Tạm biệt! Khi cần rà soát hồ sơ, bạn cứ nhắn tôi nhé."
            conversation_intent = "farewell"
        elif any(marker in normalized_question for marker in ("cảm ơn", "thanks", "thank you")):
            greeting_text = "Không có gì. Tôi luôn sẵn sàng hỗ trợ bạn rà soát hồ sơ."
            conversation_intent = "thanks"
        elif "bạn" in normalized_question and any(marker in normalized_question for marker in ("giúp", "hỗ trợ", "làm được", "khả năng")):
            greeting_text = "Tôi có thể tra cứu, đối chiếu và tóm tắt thông tin lâm sàng có dẫn nguồn trong hồ sơ hiện tại."
            conversation_intent = "capability"
        else:
            greeting_text = "Xin chào! Tôi là AI Co-pilot hỗ trợ rà soát hồ sơ bệnh án. Tôi có thể giúp gì cho bạn hôm nay?"
            conversation_intent = "greeting"
        if runtime.available:
            try:
                gen_result = runtime.client.generate_claims(
                    request.question,
                    {"info": "conversation", "intent": conversation_intent},
                )
                if gen_result and gen_result.get("summary"):
                    greeting_text = gen_result["summary"]
                elif gen_result and gen_result.get("claims"):
                    greeting_text = gen_result["claims"][0].get("text", greeting_text)
            except Exception:
                pass
        proposed = [
            ProposedClaim(
                claim_id="clm_greeting_1",
                text=greeting_text,
                evidence_ids=[],
                section_code="patient_overview"
            )
        ]
        unsupported = []
        conflicts = []
    elif isinstance(qt, dict) and qt.get("task_type") == "conflict_check" and not state.get("conflicts"):
        from src.agents.generation import ProposedClaim
        proposed = [ProposedClaim(
            claim_id="clm_no_true_conflict",
            text="Không phát hiện xung đột thực sự giữa các nguồn trong dữ liệu hiện có.",
            evidence_ids=[], section_code="changes_to_review",
        )]
        unsupported = []
        conflicts = []
    elif isinstance(qt, dict) and qt.get("comparison_required"):
        from src.agents.generation import compose_comparison_claims
        proposed = compose_comparison_claims(retrieved)
        if not proposed:
            proposed = compose_atomic_claims(retrieved)
        unsupported = []
        conflicts = state.get("conflicts", [])
    elif isinstance(qt, dict) and any(
        need.get("temporal", {}).get("intent") == "trend" for need in qt.get("needs", [])
    ) and not runtime.available:
        from src.agents.generation import compose_trend_claims
        proposed = compose_trend_claims(retrieved)
        unsupported = []
        conflicts = state.get("conflicts", [])
    elif runtime.available:
        gen_result = compose_atomic_claims_llm(
            retrieved,
            runtime.client,
            question=request.question if request.task_type == "ask_chart" else None,
        )
        proposed = gen_result["claims"]
        unsupported = gen_result["unsupported_claims"]
        conflicts = state.get("conflicts", []) + gen_result.get("conflicts", [])
    else:
        proposed = compose_atomic_claims(retrieved)
        unsupported = []
        conflicts = state.get("conflicts", [])

    return {
        "proposed_claims": proposed,
        "unsupported_claims": unsupported,
        "conflicts": conflicts
    }


def verify_claims_node(state: ClinicalReviewState) -> dict:
    claims, verification_results = verify_claims(
        state.get("proposed_claims", []),
        state.get("retrieved_evidence", []),
    )
    qt = state.get("question_type")
    is_conversational = isinstance(qt, dict) and (
        qt.get("task_type") == "conversation" or not qt.get("retrieval_required", True)
        or (qt.get("task_type") == "conflict_check" and not state.get("conflicts"))
    )
    
    if not claims:
        status = "not_found"
    elif not is_conversational and (state.get("conflicts") or any(claim.status == "needs_verification" for claim in claims)):
        status = "conflicting"
    else:
        status = "answered"
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
    
    # unsupported_claims from state must be wrapped as VerifiedClaim with status "unsupported"
    unsupported_proposed = state.get("unsupported_claims", [])
    unsupported_verified = []
    from src.agents.contracts import VerifiedClaim
    if unsupported_proposed and not isinstance(unsupported_proposed[0], VerifiedClaim):
        # they are still ProposedClaim, map to VerifiedClaim
        for uc in unsupported_proposed:
            unsupported_verified.append(VerifiedClaim(
                claim_id=uc.claim_id,
                text=uc.text,
                status="unsupported",
                confidence="low",
                citations=[],
                generator_version="wp2-grounded@1.0.0"
            ))
    else:
        unsupported_verified = unsupported_proposed

    conflicts = state.get("conflicts", [])
    status = state.get("status", "error")
    qt = state.get("question_type")
    is_conversational = isinstance(qt, dict) and (
        qt.get("task_type") == "conversation" or not qt.get("retrieval_required", True)
        or (qt.get("task_type") == "conflict_check" and not state.get("conflicts"))
    )
    citations = [] if is_conversational else _deduplicate_citations(claims)
    answer = None
    sections = None
    qt = state.get("question_type")
    is_conversational = isinstance(qt, dict) and (
        qt.get("task_type") == "conversation" or not qt.get("retrieval_required", True)
        or (qt.get("task_type") == "conflict_check" and not state.get("conflicts"))
    )
    
    if request.task_type == "ask_chart":
        if status in {"answered", "conflicting"}:
            if is_conversational:
                answer = "\n".join(claim.text for claim in claims)
            else:
                answer = "\n".join(f"- {claim.text}" for claim in claims)
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
        unsupported_claims=unsupported_verified,
        conflicts=conflicts,
        citations=citations,
        errors=state.get("errors", []),
    )
    return {"public_response": result}
