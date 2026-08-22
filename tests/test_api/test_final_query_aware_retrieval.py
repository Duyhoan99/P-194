"""Hold-out behavior tests; sentences in this module must not enter rule code."""

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_demo_repository
from src.clinical.demo_repository import DemoRepository
from src.config import get_settings
from src.main import app

ASK = "/api/v1/patients/PAT-001/ask"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_GENERATION_BACKEND", "deterministic")
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()
    repo = DemoRepository()
    app.dependency_overrides[get_demo_repository] = lambda: repo
    try:
        with TestClient(app) as test_client:
            yield test_client, repo
    finally:
        app.dependency_overrides.pop(get_demo_repository, None)
        get_settings.cache_clear()


def _ask(client: TestClient, question: str) -> dict:
    response = client.post(ASK, json={"question": question})
    assert response.status_code == 200
    return response.json()


def test_unseen_social_and_low_information_messages_do_not_retrieve(client):
    api, _ = client
    capability = _ask(api, "Bạn hỗ trợ được những tác vụ nào?")
    unclear = _ask(api, "Rồi sao nữa?")
    for body in (capability, unclear):
        assert body["status"] == "answered"
        assert body["citations"] == []
        assert "HbA1c" not in body["answer"]


@pytest.mark.parametrize(
    ("question", "required", "forbidden"),
    [
        ("Những bệnh lý đang được quản lý gồm những gì?", "Chẩn đoán", "Metformin"),
        ("Lịch sử dùng thuốc diễn biến ra sao?", "Thuốc", "HbA1c"),
        ("Diễn biến sử dụng metformin qua các lần ghi nhận?", "Metformin", "Amlodipine"),
        ("Theo thời gian, creatinin biến chuyển ra sao?", "Creatinine", "Glucose"),
        ("Cho biết diễn tiến của hemoglobin A1c trong hồ sơ.", "HbA1c", "Creatinine"),
    ],
)
def test_unseen_focused_queries_stay_in_their_domain_and_entity(
    client, question: str, required: str, forbidden: str
):
    api, _ = client
    body = _ask(api, question)
    assert body["status"] in {"answered", "conflicting"}
    assert body["citations"]
    assert required.casefold() in body["answer"].casefold()
    assert forbidden.casefold() not in body["answer"].casefold()


def test_unseen_glucose_comparison_keeps_window_and_two_endpoints(client):
    api, _ = client
    body = _ask(api, "Đối chiếu đường máu hiện tại với sáu tháng về trước.")
    assert body["status"] == "answered"
    assert len(body["citations"]) == 2
    assert "glucose" in body["answer"].casefold()
    assert "2026-01-10" in body["answer"] and "2026-06-10" in body["answer"]
    assert "HbA1c" not in body["answer"] and "Chẩn đoán" not in body["answer"]


def test_unseen_conflict_check_returns_none_without_record_dump(client):
    api, _ = client
    body = _ask(api, "Các nguồn có điểm nào không nhất quán với nhau chăng?")
    assert body["status"] == "answered"
    assert body["citations"] == []
    assert "Không phát hiện xung đột thực sự" in body["answer"]
    assert "Metformin" not in body["answer"]


def test_unseen_conflict_check_returns_only_true_pair_with_both_citations(client):
    api, repo = client
    repo.add_pdf_evidence("PAT-001", "DOC-CONFLICT-HOLDOUT", [
        {
            "patient_id": "PAT-001", "tenant_id": "ten_demo",
            "evidence_id": "ev_holdout_a", "fact_type": "timeline_observation",
            "source_time": "2026-08-10T09:00:00+07:00", "verification_status": "verified",
            "normalized_value": {"concept": "HbA1c", "statement": "HbA1c 7.4 % ngày 2026-08-10"},
            "source_value": {"title": "Xét nghiệm: HbA1c", "summary": "Kết quả: 7.4 %"},
            "citations": [{"citation_id": "cit_holdout_a", "source_type": "canonical_record", "source_record_id": "holdout_a", "source_time": "2026-08-10T09:00:00+07:00", "snippet": "HbA1c 7.4 %"}],
        },
        {
            "patient_id": "PAT-001", "tenant_id": "ten_demo",
            "evidence_id": "ev_holdout_b", "fact_type": "timeline_observation",
            "source_time": "2026-08-10T09:05:00+07:00", "verification_status": "verified",
            "normalized_value": {"concept": "HbA1c", "statement": "HbA1c 9.1 % ngày 2026-08-10"},
            "source_value": {"title": "Xét nghiệm: HbA1c", "summary": "Kết quả: 9.1 %"},
            "citations": [{"citation_id": "cit_holdout_b", "source_type": "canonical_record", "source_record_id": "holdout_b", "source_time": "2026-08-10T09:05:00+07:00", "snippet": "HbA1c 9.1 %"}],
        },
    ])
    body = _ask(api, "Có nguồn lâm sàng nào trái ngược với nguồn khác chăng?")
    assert body["status"] == "conflicting"
    assert len(body["citations"]) == 2
    assert "7.4" in body["answer"] and "9.1" in body["answer"]
    assert "Metformin" not in body["answer"]


def test_unseen_summary_remains_bounded_and_multidomain(client):
    api, _ = client
    body = _ask(api, "Hãy tổng quan những điểm y khoa đáng chú ý trong ca bệnh.")
    assert body["status"] in {"answered", "conflicting"}
    assert 2 <= len(body["citations"]) <= 15
    assert "Chẩn đoán" in body["answer"] and "Thuốc" in body["answer"]
