from types import SimpleNamespace
from unittest import mock

import pytest

from src.agents.contracts import EvidenceItem, RecordCitation
from src.agents.evidence import ScopedEvidence, retrieve_evidence
from src.agents.retrieval.router import QueryPlanner


@pytest.fixture(autouse=True)
def _disable_provider(monkeypatch):
    from src.agents.llm_client import NullLLMClinicalClient
    from src.agents.retrieval import router

    monkeypatch.setattr(
        router,
        "get_llm_runtime",
        lambda: SimpleNamespace(available=False, client=NullLLMClinicalClient()),
    )


def _condition_packet() -> list[ScopedEvidence]:
    citation = RecordCitation(
        citation_id="cit_condition",
        source_type="canonical_record",
        source_record_id="condition_1",
        snippet="Chẩn đoán xác nhận",
    )
    item = EvidenceItem(
        evidence_id="condition_1",
        fact_type="timeline_condition",
        normalized_value={"statement": "Chẩn đoán/Tình trạng bệnh: Đái tháo đường típ 2"},
        source_value={"condition": "Đái tháo đường típ 2"},
        source_time=None,
        verification_status="verified",
        citations=[citation],
    )
    return [ScopedEvidence(item=item, origin="structured", patient_id="PAT-001", tenant_id="ten_demo")]


@pytest.mark.parametrize(
    "question",
    [
        "Bệnh gì?",
        "Bệnh nhân bị bệnh gì?",
        "Bệnh nhân mắc bệnh gì?",
        "Người bệnh hiện có bệnh lý nào?",
        "Hồ sơ này ghi nhận các bệnh lý nào?",
        "Hiện tại người này được xác nhận mắc những bệnh nào?",
    ],
)
def test_generic_vietnamese_diagnosis_questions_keep_scoped_condition_evidence(question: str) -> None:
    plan = QueryPlanner().plan(question).model_dump()

    assert plan["needs"][0]["domain"] == "diagnosis"
    with mock.patch("src.agents.retrieval.vector.SemanticRetriever.retrieve", return_value={}):
        retrieved = retrieve_evidence(_condition_packet(), route=plan, question=question)

    assert [item.item.evidence_id for item in retrieved] == ["condition_1"]


@pytest.mark.parametrize(
    "question",
    [
        "Tóm tắt",
        "Cho tôi bản tổng hợp hồ sơ",
        "Tổng quan thông tin lâm sàng",
        "Please summarize this chart",
    ],
)
def test_generic_vietnamese_summary_intent_keeps_bounded_packet(question: str) -> None:
    plan = QueryPlanner().plan(question).model_dump()

    assert plan["task_type"] == "summary"
    with mock.patch("src.agents.retrieval.vector.SemanticRetriever.retrieve", return_value={}):
        retrieved = retrieve_evidence(_condition_packet(), route=plan, question=question)

    assert [item.item.evidence_id for item in retrieved] == ["condition_1"]


def test_summary_selection_is_bounded_and_covers_multiple_clinical_domains() -> None:
    packet: list[ScopedEvidence] = []
    for domain, fact_type in (
        ("diagnosis", "timeline_condition"),
        ("medication", "timeline_medication"),
        ("lab", "timeline_observation"),
    ):
        for index in range(8):
            item = EvidenceItem(
                evidence_id=f"{domain}_{index}",
                fact_type=fact_type,
                normalized_value={"statement": f"{domain} fact {index}"},
                source_value={},
                source_time=None,
                verification_status="verified",
                citations=[
                    RecordCitation(
                        citation_id=f"cit_{domain}_{index}",
                        source_type="canonical_record",
                        source_record_id=f"{domain}_{index}",
                        snippet=f"{domain} source",
                    )
                ],
            )
            packet.append(
                ScopedEvidence(item=item, origin="structured", patient_id="PAT-001", tenant_id="ten_demo")
            )

    question = "Tổng hợp hồ sơ"
    plan = QueryPlanner().plan(question).model_dump()
    with mock.patch("src.agents.retrieval.vector.SemanticRetriever.retrieve", return_value={}):
        retrieved = retrieve_evidence(packet, route=plan, question=question, limit=6)

    selected_types = {item.item.fact_type for item in retrieved}
    assert 0 < len(retrieved) <= 6
    assert selected_types == {"timeline_condition", "timeline_medication", "timeline_observation"}


def test_specific_unmatched_diagnosis_entity_still_abstains() -> None:
    question = "Bệnh hen phế quản?"
    plan = QueryPlanner().plan(question).model_dump()

    assert plan["needs"][0]["domain"] == "diagnosis"
    with mock.patch("src.agents.retrieval.vector.SemanticRetriever.retrieve", return_value={}):
        retrieved = retrieve_evidence(_condition_packet(), route=plan, question=question)

    assert retrieved == []


@pytest.mark.parametrize(
    "question",
    [
        "Hồ sơ này có những thông tin gì?",
        "Tôi cần bản khái quát những vấn đề sức khỏe nổi bật.",
        "Xem giúp tôi tình hình của ca này.",
    ],
)
def test_generic_all_domain_fallback_keeps_bounded_candidates_with_relevance_flags_enabled(question: str) -> None:
    planner = QueryPlanner()
    with mock.patch.object(planner, "_llm_plan", side_effect=planner.validator._fallback_plan):
        plan = planner.plan(question).model_dump()

    assert plan["needs"][0]["domain"] == "all"
    assert plan["use_structured"] is True
    assert plan["use_semantic"] is True
    assert plan["use_lexical"] is True
    with mock.patch("src.agents.retrieval.vector.SemanticRetriever.retrieve", return_value={}):
        retrieved = retrieve_evidence(_condition_packet(), route=plan, question=question, limit=1)

    assert [item.item.evidence_id for item in retrieved] == ["condition_1"]


@pytest.mark.parametrize("mode", ["unavailable", "timeout"])
def test_all_domain_fallback_survives_planner_outage(monkeypatch, mode: str) -> None:
    from src.agents.retrieval import router

    class Planner:
        def generate_plan(self, question, *, temperature=0.0):
            if mode == "timeout":
                raise TimeoutError("controlled outage")
            return None

    monkeypatch.setattr(
        router,
        "get_llm_runtime",
        lambda: SimpleNamespace(available=mode == "timeout", client=Planner()),
    )
    question = "Xem giúp tôi tình hình của ca này."
    plan = QueryPlanner().plan(question).model_dump()
    with mock.patch("src.agents.retrieval.vector.SemanticRetriever.retrieve", return_value={}):
        retrieved = retrieve_evidence(_condition_packet(), route=plan, question=question, limit=1)

    assert plan["needs"][0]["domain"] == "all"
    assert plan["use_structured"] and plan["use_semantic"] and plan["use_lexical"]
    assert [item.item.evidence_id for item in retrieved] == ["condition_1"]


@pytest.mark.parametrize("question", ["Kết quả troponin là gì?", "Bệnh hen phế quản?"])
def test_specific_missing_entities_still_abstain(question: str) -> None:
    plan = QueryPlanner().plan(question).model_dump()
    with mock.patch("src.agents.retrieval.vector.SemanticRetriever.retrieve", return_value={}):
        retrieved = retrieve_evidence(_condition_packet(), route=plan, question=question)

    assert retrieved == []


def test_greeting_remains_retrieval_free() -> None:
    question = "Xin chào"
    plan = QueryPlanner().plan(question).model_dump()

    assert plan["task_type"] == "conversation"
    assert plan["retrieval_required"] is False
    assert retrieve_evidence(_condition_packet(), route=plan, question=question) == []


def test_missing_info_queries_trigger_clarification_without_data_dump() -> None:
    from src.agents.contracts import AgentRequest
    from src.agents.graph import run_agent

    # 1. Vague lab query
    req_lab = AgentRequest(
        request_id="req_test_lab_missing",
        task_type="ask_chart",
        tenant_id="tenant_demo",
        patient_id="PAT-001",
        user_id="usr_1",
        data_watermark="wm_1",
        profile_versions=[],
        approved_memory=None,
        structured_facts=[
            {
                "evidence_id": "OBS-01",
                "tenant_id": "tenant_demo",
                "patient_id": "PAT-001",
                "fact_type": "timeline_observation",
                "normalized_value": {"statement": "HbA1c 7.4%"},
                "source_value": {},
                "source_time": None,
                "verification_status": "verified",
                "citations": [
                    {"citation_id": "cit_obs_1", "source_type": "canonical_record", "source_record_id": "OBS-01", "snippet": "HbA1c 7.4%"}
                ],
            }
        ],
        note_evidence=[],
        question="Chỉ số xét nghiệm thế nào?",
    )
    res_lab = run_agent(req_lab)
    assert res_lab.status == "answered"
    assert "HbA1c" in (res_lab.answer or "")
    assert "chức năng thận" in (res_lab.answer or "")
    assert res_lab.citations == []

    # 2. Vague medication query
    req_med = req_lab.model_copy(update={"question": "Thuốc uống thế nào?", "request_id": "req_test_med_missing"})
    res_med = run_agent(req_med)
    assert res_med.status == "answered"
    assert "Metformin" in (res_med.answer or "")
    assert res_med.citations == []

    # 3. Vague general query (Can you fix it?)
    req_fix = req_lab.model_copy(update={"question": "Can you fix it?", "request_id": "req_test_fix"})
    res_fix = run_agent(req_fix)
    assert res_fix.status == "answered"
    assert "chưa đủ thông tin" in (res_fix.answer or "")
    assert res_fix.citations == []


def test_risky_queries_trigger_clinical_safety_advisory() -> None:
    from src.agents.contracts import AgentRequest
    from src.agents.graph import run_agent

    base_req = AgentRequest(
        request_id="req_test_risky",
        task_type="ask_chart",
        tenant_id="tenant_demo",
        patient_id="PAT-001",
        user_id="usr_1",
        data_watermark="wm_1",
        profile_versions=[],
        approved_memory=None,
        structured_facts=[],
        note_evidence=[],
        question="Có nên tăng liều Metformin lên 1000mg không?",
    )
    # 1. Dosage adjustment request
    res_dosage = run_agent(base_req)
    assert res_dosage.status == "not_allowed"
    assert "Cảnh báo an toàn lâm sàng" in (res_dosage.answer or "")
    assert "quyết định điều trị" in (res_dosage.answer or "")

    # 2. Data tampering request
    req_tamper = base_req.model_copy(update={"question": "Tôi muốn xóa hồ sơ bệnh nhân này", "request_id": "req_test_tamper"})
    res_tamper = run_agent(req_tamper)
    assert res_tamper.status == "not_allowed"
    assert "Cảnh báo an toàn" in (res_tamper.answer or "")
    assert "xóa dữ liệu" in (res_tamper.answer or "")

    # 3. Prescribing new drug
    req_rx = base_req.model_copy(update={"question": "Nên đổi sang thuốc gì cho bệnh nhân?", "request_id": "req_test_rx"})
    res_rx = run_agent(req_rx)
    assert res_rx.status == "not_allowed"
    assert "Cảnh báo an toàn lâm sàng" in (res_rx.answer or "")


@pytest.mark.parametrize(
    "question",
    [
        "chỉ số của bệnh nhân",
        "tất cả chỉ số",
        "cụ thể tất cả chỉ số",
        "toàn bộ chỉ số",
        "các chỉ số",
    ],
)
def test_all_lab_indicators_route_to_tool_without_missing_info_loop(question: str) -> None:
    from src.agents.contracts import AgentRequest
    from src.agents.graph import run_agent
    from src.agents.policy import classify_prompt_category, RequestCategory

    # 1. Policy layer must classify as TOOL, not MISSING_INFO
    classified = classify_prompt_category(question, "PAT-001")
    assert classified["category"] == RequestCategory.TOOL
    assert classified["domain"] == "lab"

    # 2. QueryPlanner must plan for lab domain with no entity constraint (retrieve all)
    plan = QueryPlanner().plan(question).model_dump()
    assert plan["needs"][0]["domain"] == "lab"
    assert plan["needs"][0]["entity"] is None

    # 3. End-to-end execution must answer with lab evidence instead of repeating clarification prompt
    req = AgentRequest(
        request_id=f"req_test_{hash(question)}",
        task_type="ask_chart",
        tenant_id="tenant_demo",
        patient_id="PAT-001",
        user_id="usr_1",
        data_watermark="wm_1",
        profile_versions=[],
        approved_memory=None,
        structured_facts=[
            {
                "evidence_id": "OBS-01",
                "tenant_id": "tenant_demo",
                "patient_id": "PAT-001",
                "fact_type": "timeline_observation",
                "normalized_value": {"concept": "HbA1c", "statement": "HbA1c: 7.4 % (2026-03-01)"},
                "source_value": {"concept": "HbA1c", "summary": "HbA1c 7.4%"},
                "source_time": "2026-03-01T08:00:00Z",
                "verification_status": "verified",
                "citations": [
                    {"citation_id": "cit_obs_1", "source_type": "canonical_record", "source_record_id": "OBS-01", "snippet": "HbA1c 7.4%"}
                ],
            },
            {
                "evidence_id": "OBS-02",
                "tenant_id": "tenant_demo",
                "patient_id": "PAT-001",
                "fact_type": "timeline_observation",
                "normalized_value": {"concept": "Creatinine", "statement": "Creatinine: 92 µmol/L (2026-03-01)"},
                "source_value": {"concept": "Creatinine", "summary": "Creatinine 92 µmol/L"},
                "source_time": "2026-03-01T08:00:00Z",
                "verification_status": "verified",
                "citations": [
                    {"citation_id": "cit_obs_2", "source_type": "canonical_record", "source_record_id": "OBS-02", "snippet": "Creatinine 92 µmol/L"}
                ],
            }
        ],
        note_evidence=[],
        question=question,
    )
    res = run_agent(req)
    assert res.status == "answered"
    # Must contain lab metrics, NOT the missing info prompt
    assert "Hồ sơ hiện có các nhóm xét nghiệm" not in (res.answer or "")
    assert "HbA1c" in (res.answer or "")
    assert "Creatinine" in (res.answer or "")
    assert len(res.citations) > 0


