from unittest import mock
from types import SimpleNamespace

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
