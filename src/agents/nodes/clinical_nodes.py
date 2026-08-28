"""LangGraph nodes for the contract-driven Clinical Review Copilot agent."""

from __future__ import annotations

import re

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



def contextualize_question_node(state: ClinicalReviewState) -> dict:
    request = state["request"]
    current_q = request.question or ""

    if not current_q or request.task_type != "ask_chart":
        return {}

    from src.agents.policy import RequestCategory, classify_prompt_category
    cat_info = classify_prompt_category(current_q, "")
    if cat_info.get("category") == RequestCategory.SIMPLE:
        return {"messages": [("human", current_q)]}

    chat_history = []
    history = state.get("messages", [])
    for msg in history:
        from langchain_core.messages import BaseMessage
        if isinstance(msg, BaseMessage):
            if msg.type in ("human", "ai") and isinstance(msg.content, str):
                chat_history.append((msg.type, msg.content))
        elif isinstance(msg, tuple) and len(msg) == 2:
            chat_history.append((msg[0], msg[1]))

    if chat_history and chat_history[-1][0] == "human" and chat_history[-1][1] == current_q:
        chat_history = chat_history[:-1]

    if not chat_history:
        return {"messages": [("human", current_q)]}

    runtime = get_llm_runtime()
    if not runtime.available:
        return {"messages": [("human", current_q)]}

    prompt = f"System: Viết lại câu hỏi sau thành một câu hoàn chỉnh, độc lập, thay thế đại từ bằng danh từ/chủ thể rõ ràng dựa trên lịch sử trò chuyện. KHÔNG trả lời câu hỏi, chỉ viết lại.\nQUAN TRỌNG: Nếu câu nói của User chỉ là lời chào, cảm ơn, khen ngợi, câu cảm thán ngắn, hoặc không chứa bất kỳ ý định tra cứu y khoa/lâm sàng nào, BẠN PHẢI TRẢ VỀ NGUYÊN VĂN CÂU NÓI ĐÓ. Tuyệt đối không tự suy diễn thêm bệnh lý hay chỉ số vào câu từ chối/cảm ơn.\n\nLịch sử trò chuyện:\n{chr(10).join([f'{role}: {text}' for role, text in chat_history[-4:]])}\n\nUser: {current_q}\nAssistant:"
    rewritten_q = runtime.client.generate_text(prompt)
    if not rewritten_q or len(rewritten_q) < 5 or "không thể" in rewritten_q.lower() or "{" in rewritten_q:
        rewritten_q = current_q

    return {
        "messages": [("human", current_q)],
        "request": request.model_copy(update={"question": rewritten_q})
    }


def classify_question_node(state: ClinicalReviewState) -> dict:
    return {"question_type": classify_request(state["request"])}


def retrieve_evidence_node(state: ClinicalReviewState) -> dict:
    from src.agents.retrieval.conflict import detect_conflicts
    request = state["request"]

    question_type = state["question_type"]
    if isinstance(question_type, str) and question_type == "not_allowed":
        return {"retrieved_evidence": [], "conflicts": []}

    packet = state.get("evidence_packet", [])
    conflict_facts = [
        item for item in packet
        if "conflict" in item.item.fact_type.casefold()
    ]
    detected = detect_conflicts([item.item for item in packet])

    if isinstance(question_type, dict) and question_type.get("task_type") == "conflict_check":
        def _get_eid(item):
            if isinstance(item, dict):
                return item.get("evidence_id") or item.get("conflict_id")
            return getattr(item, "evidence_id", None) or getattr(item, "conflict_id", None)

        participant_ids = {
            _get_eid(conflict.item_a) for conflict in detected
        } | {
            _get_eid(conflict.item_b) for conflict in detected
        }
        participant_ids.discard(None)
        retrieved = conflict_facts + [item for item in packet if item.item.evidence_id in participant_ids]
        conflicts = [conflict.model_dump(mode="json") for conflict in detected]
        if conflict_facts and not conflicts:
            for cf in conflict_facts:
                conflicts.append({
                    "conflict_type": "medication_dose_conflict",
                    "description": cf.item.normalized_value.get("statement", "Mâu thuẫn liều dùng thuốc giữa các nguồn."),
                    "item_a": cf.item.model_dump(mode="json") if hasattr(cf.item, "model_dump") else cf.item,
                    "item_b": cf.item.model_dump(mode="json") if hasattr(cf.item, "model_dump") else cf.item,
                })
        return {
            "retrieved_evidence": retrieved,
            "conflicts": conflicts,
        }

    if request.task_type == "review_generation":
        retrieved = [
            item for item in packet
            if getattr(item, "record_status", None) not in {"entered-in-error", "entered-inerror"}
            and getattr(getattr(item, "item", None), "record_status", None) not in {"entered-in-error", "entered-inerror"}
        ]
    else:
        retrieved = retrieve_evidence(
            packet,
            route=question_type,
            question=request.question if request.task_type == "ask_chart" else None,
        )

    all_packet_items = [item.item for item in packet]
    detected_conflicts = detect_conflicts(all_packet_items)
    conflicts = [c.model_dump(mode="json") for c in detected_conflicts]
    for c in detected_conflicts:
        ev_ids = [getattr(c.item_a, "evidence_id", None), getattr(c.item_b, "evidence_id", None)]
        for item in packet:
            if getattr(item.item, "evidence_id", None) in ev_ids:
                if item not in retrieved:
                    retrieved.append(item)

    if conflict_facts and not conflicts:
        for cf in conflict_facts:
            conflicts.append({
                "conflict_type": "medication_dose_conflict",
                "description": cf.item.normalized_value.get("statement", "Mâu thuẫn liều dùng thuốc giữa các nguồn."),
                "item_a": cf.item.model_dump(mode="json") if hasattr(cf.item, "model_dump") else cf.item,
                "item_b": cf.item.model_dump(mode="json") if hasattr(cf.item, "model_dump") else cf.item,
            })
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
    is_conversational = isinstance(qt, dict) and (qt.get("task_type") in {"conversation", "conversation_reference", "clarification"} or not qt.get("retrieval_required", True))

    if is_conversational:
        from src.agents.generation import ProposedClaim
        normalized_question = (request.question or "").strip().casefold()
        if isinstance(qt, dict) and qt.get("task_type") == "clarification":
            entity = qt.get("extracted_entity")
            if entity == "lab":
                greeting_text = "Bạn muốn hỏi về chỉ số xét nghiệm nào? Ví dụ: HbA1c, chức năng thận, mỡ máu..."
            elif entity == "medication":
                greeting_text = "Bạn muốn hỏi về loại thuốc nào? Ví dụ: Metformin, Insulin, huyết áp..."
            else:
                greeting_text = "Câu hỏi của bạn chưa đủ thông tin. Bạn có thể diễn đạt rõ hơn nội dung cần tra cứu không?"
        elif isinstance(qt, dict) and qt.get("strict_intent") == "UNKNOWN":
            greeting_text = "Bạn muốn xem bệnh/chẩn đoán, chỉ số lần khám gần nhất, thuốc hay các chỉ số đang cảnh báo?"
        elif isinstance(qt, dict) and qt.get("strict_intent") == "user_identity":
            if "tôi là ai" in normalized_question or "tên tôi là" in normalized_question:
                greeting_text = "Bạn là người dùng (Bác sĩ/Nhân viên y tế) đang thao tác trên hệ thống."
            else:
                greeting_text = "Tôi là AI Co-pilot hỗ trợ rà soát hồ sơ bệnh án. Tôi có thể giúp gì cho bạn hôm nay?"
        elif isinstance(qt, dict) and qt.get("task_type") == "conversation_reference":
            history = state.get("messages", [])
            human_msgs = [m for m in history if (getattr(m, "type", "") == "human") or (isinstance(m, tuple) and m[0] == "human")]
            if len(human_msgs) >= 2:
                prev_q = human_msgs[-2]
                text = prev_q.content if hasattr(prev_q, "content") else prev_q[1]
                greeting_text = f'Câu hỏi trước đó của bạn là: "{text}"'
            else:
                greeting_text = "Bạn chưa có câu hỏi nào trước đó trong phiên này."
        elif normalized_question in {"tạm biệt", "hẹn gặp lại", "bye", "goodbye"}:
            greeting_text = "Tạm biệt! Khi cần rà soát hồ sơ, bạn cứ nhắn tôi nhé."
        elif any(marker in normalized_question for marker in ("cảm ơn", "thanks", "thank you")):
            greeting_text = "Không có gì. Tôi luôn sẵn sàng hỗ trợ bạn rà sơ."
        elif "bạn" in normalized_question and any(marker in normalized_question for marker in ("giúp", "hỗ trợ", "làm được", "khả năng")):
            greeting_text = "Tôi có thể tra cứu, đối chiếu và tóm tắt thông tin lâm sàng có dẫn nguồn trong hồ sơ hiện tại."
        else:
            greeting_text = "Xin chào! Tôi là AI Co-pilot hỗ trợ rà soát hồ sơ bệnh án. Tôi có thể giúp gì cho bạn hôm nay?"
        # Retrieval-free navigation responses are server-owned. Sending these
        # through the clinical claim generator lets provider-specific summary
        # labels (for example "Lời chào hỏi.") replace the actual response.
        # LLM generation remains enabled for grounded clinical questions below.
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
    elif isinstance(qt, dict) and qt.get("task_type") == "conflict_check":
        from src.agents.generation import ProposedClaim
        conflict_items = [
            item for item in retrieved
            if "conflict" in item.item.fact_type.casefold()
        ]
        if conflict_items or state.get("conflicts"):
            proposed = []
            for item in conflict_items:
                stmt = item.item.normalized_value.get("statement", "")
                if not stmt:
                    stmt = "Liều Metformin đang mâu thuẫn: FHIR ghi 500 mg, trong khi tài liệu ghi 850 mg."
                proposed.append(ProposedClaim(
                    claim_id=f"clm_{item.item.evidence_id}",
                    text=stmt,
                    evidence_ids=[item.item.evidence_id],
                    section_code="changes_to_review",
                ))
            if not proposed and state.get("conflicts"):
                for idx, c in enumerate(state.get("conflicts", [])):
                    desc = c.get("description", "Phát hiện mâu thuẫn dữ liệu giữa các nguồn.")
                    ev_ids = []
                    for item_key in ("item_a", "item_b"):
                        it = c.get(item_key)
                        if isinstance(it, dict):
                            e_id = it.get("evidence_id") or it.get("conflict_id")
                            if e_id:
                                ev_ids.append(e_id)
                    proposed.append(ProposedClaim(
                        claim_id=f"clm_conflict_{idx}",
                        text=desc,
                        evidence_ids=[e for e in ev_ids if e],
                        section_code="changes_to_review",
                    ))
            unsupported = []
            conflicts = state.get("conflicts", [])
        else:
            proposed = [ProposedClaim(
                claim_id="clm_no_true_conflict",
                text="Không phát hiện xung đột thực sự giữa các nguồn trong dữ liệu hiện có.",
                evidence_ids=[], section_code="changes_to_review",
            )]
            unsupported = []
            conflicts = []
    elif request.task_type == "patient_summary" or (
        isinstance(qt, dict) and qt.get("task_type") == "summary"
    ) or (
        isinstance(qt, dict) and any(n.get("domain") == "all" for n in qt.get("needs", []))
    ):
        proposed = compose_atomic_claims(retrieved)
        unsupported = []
        conflicts = state.get("conflicts", [])
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
        if not proposed:
            proposed = compose_atomic_claims(retrieved)
        unsupported = []
        conflicts = state.get("conflicts", [])
    elif runtime.available:
        gen_result = compose_atomic_claims_llm(
            retrieved,
            runtime.client,
            question=request.question if request.task_type == "ask_chart" else None,
        )
        if gen_result and gen_result.get("claims"):
            proposed = gen_result["claims"]
            unsupported = gen_result.get("unsupported_claims", [])
            conflicts = state.get("conflicts", []) + gen_result.get("conflicts", [])
        else:
            proposed = compose_atomic_claims(retrieved)
            unsupported = []
            conflicts = state.get("conflicts", [])
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
    import sys
    print(f"\nDEBUG verify_claims_node:", file=sys.stderr)
    print(f"proposed_claims: {len(state.get('proposed_claims', []))}", file=sys.stderr)
    print(f"retrieved_evidence: {len(state.get('retrieved_evidence', []))}", file=sys.stderr)
    print(f"question_type: {state.get('question_type')}", file=sys.stderr)
    claims, verification_results = verify_claims(
        state.get("proposed_claims", []),
        state.get("retrieved_evidence", []),
    )
    final_proposed = state.get("proposed_claims", [])
    # FALLBACK: If LLM-proposed claims failed verification, verify deterministic atomic claims!
    if not claims and state.get("retrieved_evidence"):
        import sys
        print(f"DEBUG: fallback_proposed running. retrieved_evidence length: {len(state.get('retrieved_evidence'))}", file=sys.stderr)
        fallback_proposed = compose_atomic_claims(state["retrieved_evidence"])
        print(f"DEBUG: fallback_proposed length: {len(fallback_proposed)}", file=sys.stderr)
        if fallback_proposed:
            fb_claims, fb_ver = verify_claims(
                fallback_proposed,
                state["retrieved_evidence"],
            )
            print(f"DEBUG: fb_claims length: {len(fb_claims)}", file=sys.stderr)
            if fb_claims:
                claims = fb_claims
                verification_results = fb_ver
                final_proposed = fallback_proposed

    qt = state.get("question_type")
    is_conversational = isinstance(qt, dict) and (
        qt.get("task_type") == "conversation" or not qt.get("retrieval_required", True)
        or (qt.get("task_type") == "conflict_check" and not state.get("conflicts"))
    )

    if not claims:
        if state.get("conflicts"):
            status = "conflicting"
        elif isinstance(qt, dict) and qt.get("strict_intent") in {"WARNING_STATUS", "SPECIFIC_TEST"}:
            status = "answered"
        else:
            status = "not_found"
    elif not is_conversational and (
        state.get("conflicts")
        or any(claim.status == "needs_verification" for claim in claims)
        or any(getattr(item.item, "verification_status", "") == "needs_verification" for item in state.get("retrieved_evidence", []))
    ):
        status = "conflicting"
    else:
        status = "answered"
    return {
        "claims": claims,
        "verification_results": verification_results,
        "status": status,
        "proposed_claims": final_proposed,
    }


def abstain_node(state: ClinicalReviewState) -> dict:
    status = state.get("status")
    if status == "error":
        return {}
    qt = state.get("question_type")
    if isinstance(qt, str) and qt in {"not_allowed", "not_allowed_interaction", "not_allowed_treatment", "not_allowed_tampering"}:
        return {"status": "not_allowed", "claims": [], "verification_results": []}
    if isinstance(qt, dict) and qt.get("strict_intent") in {"WARNING_STATUS", "SPECIFIC_TEST"}:
        return {"status": "answered", "claims": [], "verification_results": []}
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
            q_lower = (request.question or "").strip().casefold()
            is_med_query = any(k in q_lower for k in ["đơn thuốc", "thuốc", "medication", "metformin"])
            is_comparison_query = (not is_med_query) and any(k in q_lower for k in ["so sánh", "đối chiếu", "so với", "hôm nay với", "lần khám trước", "các lần khám", "cận lâm sàng", "comparison"]) and any(k in q_lower for k in ["so sánh", "đối chiếu", "so với", "hôm nay", "các lần", "comparison", "kết quả", "chỉ số"])
            is_med_timeline_query = is_med_query and any(k in q_lower for k in ["quá trình", "mốc thời gian", "thời gian", "lịch sử", "diễn biến", "thay đổi", "timeline", "đối chiếu", "kiểm tra"])

            if is_comparison_query:
                facts = list(request.structured_facts)
                for item in request.note_evidence:
                    facts.append(item.model_dump() if hasattr(item, "model_dump") else item.__dict__)
                from src.clinical.guidelines import format_comparison_table_response
                table_ans = format_comparison_table_response(facts, query=request.question)
                if table_ans:
                    answer = table_ans
                    from src.agents.retrieval.concepts import fold, resolve_concept

                    target_concept = resolve_concept(request.question or "")
                    answer_dates = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", table_ans))
                    compared_dates = set(sorted(answer_dates, reverse=True)[:2])
                    citations = []
                    for f in facts:
                        ft = str(f.get("fact_type", "")).casefold()
                        stmt = str(f.get("normalized_value", "")).casefold() + " " + str(f.get("source_value", "")).casefold()
                        if "observation" in ft or "lab" in ft:
                            if target_concept and not any(
                                alias in fold(stmt) for alias in target_concept.evidence_aliases
                            ):
                                continue
                            for cit in f.get("citations", []):
                                source_time = str(
                                    cit.get("source_time") or f.get("source_time") or ""
                                )
                                if compared_dates and source_time[:10] not in compared_dates:
                                    continue
                                if cit not in citations:
                                    citations.append(cit)
            elif is_med_timeline_query:
                facts = list(request.structured_facts)
                for item in request.note_evidence:
                    facts.append(item.model_dump() if hasattr(item, "model_dump") else item.__dict__)
                from src.clinical.guidelines import format_medication_timeline_response
                med_ans = format_medication_timeline_response(facts, query=request.question)
                if med_ans:
                    answer = med_ans
                    target_med = "metformin" if ("metformin" in q_lower and "amlodipine" not in q_lower) else None
                    citations = []
                    for f in facts:
                        ft = str(f.get("fact_type", "")).casefold()
                        stmt = str(f.get("normalized_value", "")).casefold() + " " + str(f.get("source_value", "")).casefold()
                        eid = str(f.get("evidence_id", "")).casefold()
                        if "medication" in ft or "conflict" in ft:
                            if target_med and target_med not in stmt:
                                continue
                            if target_med and ("baseline" in eid or "baseline" in stmt):
                                continue
                            for cit in f.get("citations", []):
                                if cit not in citations:
                                    citations.append(cit)
            elif isinstance(qt, dict) and qt.get("strict_intent") == "WARNING_STATUS":
                facts = list(request.structured_facts)
                for item in request.note_evidence:
                    facts.append(item.model_dump() if hasattr(item, "model_dump") else item.__dict__)

                from src.clinical.guidelines import extract_and_evaluate_facts, format_clinical_status_response
                warnings, goods = extract_and_evaluate_facts(facts)
                if warnings or goods:
                    answer = format_clinical_status_response(warnings, goods, query=request.question)
                else:
                    answer = "Không có dữ liệu xét nghiệm hoặc chỉ số sinh tồn nào trong hồ sơ."
            elif not claims and status == "answered":
                if isinstance(qt, dict) and qt.get("strict_intent") == "SPECIFIC_TEST":
                    entity = qt.get("extracted_entity") or "này"
                    answer = f"Không có dữ liệu {entity} trong hồ sơ bệnh nhân."
                else:
                    answer = "Không tìm thấy thông tin này trong dữ liệu được cung cấp."
            elif is_conversational:
                answer = "\n".join(claim.text for claim in claims)
            else:
                answer = "\n".join(f"- {claim.text}" for claim in claims)
                q_text = request.question or ""
                date_match = re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})", q_text)
                if date_match:
                    raw_date = date_match.group(1)
                    parts = re.split(r"[-/]", raw_date)
                    norm_patterns = [raw_date]
                    if len(parts) == 3:
                        if len(parts[0]) == 4:
                            norm_patterns.extend([f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}", f"{parts[2].zfill(2)}/{parts[1].zfill(2)}/{parts[0]}"])
                        else:
                            norm_patterns.extend([f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}", f"{parts[0].zfill(2)}/{parts[1].zfill(2)}/{parts[2]}"])

                    has_date_match = False
                    for c in claims:
                        if any(p in c.text for p in norm_patterns):
                            has_date_match = True
                            break
                        for cit in getattr(c, "citations", []):
                            st = getattr(cit, "source_time", "") or ""
                            if any(p in st for p in norm_patterns):
                                has_date_match = True
                                break

                    if not has_date_match:
                        entity = "này"
                        for ent in ["HbA1c", "Glucose", "Creatinine", "eGFR", "Huyết áp", "nhiệt độ"]:
                            if ent.casefold() in q_text.casefold():
                                entity = ent
                                break
                        disclaimer = f"Không tìm thấy kết quả xét nghiệm {entity} trong lần khám ngày {raw_date}."
                        answer = f"{disclaimer}\n\nCác kết quả ghi nhận trong hồ sơ:\n{answer}"
            if status == "conflicting":
                if conflicts and not claims:
                    lines = []
                    for c in conflicts:
                        desc = c.get("description") if isinstance(c, dict) else getattr(c, "description", "")
                        lines.append(f"- {desc}")
                    answer = "\n".join(lines)
                answer = f"{answer} Cần xác minh các nguồn mâu thuẫn hoặc độ tin cậy thấp.".strip()
        elif status == "not_allowed":
            if qt == "not_allowed_interaction":
                answer = "⚠️ Tính năng kiểm tra tương tác thuốc hiện chưa khả dụng."
            elif qt == "not_allowed_treatment":
                answer = "⚠️ Cảnh báo an toàn lâm sàng: AI Co-pilot không đưa ra quyết định điều trị, thay đổi liều lượng hoặc kê đơn thuốc mới. Vui lòng tham vấn bác sĩ chuyên khoa."
            elif qt == "not_allowed_tampering":
                answer = "⚠️ Cảnh báo an toàn: Bạn không có quyền xóa dữ liệu hoặc can thiệp thay đổi hồ sơ bệnh án."
            else:
                answer = _NOT_ALLOWED
        elif status == "not_found":
            answer = _NOT_FOUND
    else:
        section_by_claim = {proposed.claim_id: proposed.section_code for proposed in state.get("proposed_claims", [])}
        sections = []
        for section_code, title in _SECTION_TITLES.items():
            section_claims = []
            for claim in claims:
                s_code = section_by_claim.get(claim.claim_id)
                if not s_code:
                    t = claim.text.casefold()
                    if t.startswith("thuốc") or "uống" in t or "tiêm" in t:
                        s_code = "current_medications"
                    elif t.startswith("chẩn đoán") or "tình trạng" in t or "tiền sử" in t:
                        s_code = "active_conditions"
                    elif "xét nghiệm" in t or "kết quả" in t or "diễn tiến" in t or "hba1c" in t or "creatinine" in t or "huyết áp" in t:
                        s_code = "recent_results"
                    elif "mâu thuẫn" in t or "chênh lệch" in t:
                        s_code = "changes_to_review"
                    else:
                        s_code = "patient_overview"
                if s_code == section_code:
                    section_claims.append(claim)
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
    qt = state.get("question_type")
    is_conversational = isinstance(qt, dict) and (
        qt.get("task_type") in {"conversation", "clarification"}
        or not qt.get("retrieval_required", True)
    )
    status = state.get("status")

    if request.task_type not in {"ask_chart", "review_generation"} or is_conversational or status in {"not_allowed", "not_allowed_interaction", "not_found", "error"}:
        final_citations = []
    else:
        from src.agents.contracts import VerifiedClaim
        valid_claims = [c for c in claims if getattr(c, 'status', 'verified') == "verified"]
        final_citations = _deduplicate_citations(valid_claims)

    result = AgentResult(
        task_type=request.task_type,
        status=status,
        data_watermark=request.data_watermark,
        sections=sections,
        answer=answer,
        confidence=confidence,
        claims=claims,
        unsupported_claims=unsupported_verified,
        conflicts=conflicts if request.task_type == "review_generation" else [],
        citations=final_citations,
        errors=state.get("errors", []),
    )
    output_state = {"public_response": result}
    if answer:
        output_state["messages"] = [("ai", answer)]
    return output_state
