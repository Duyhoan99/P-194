"""Unseen final-polish tests. Keep these complete sentences out of rule code."""

from fastapi.testclient import TestClient
import pytest

from src.agents.contracts import EvidenceItem
from src.agents.retrieval.conflict import detect_conflicts
from src.api.dependencies import get_demo_repository
from src.clinical.demo_repository import DemoRepository
from src.config import get_settings
from src.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_GENERATION_BACKEND", "deterministic")
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()
    app.dependency_overrides[get_demo_repository] = lambda: DemoRepository()
    try:
        with TestClient(app) as api:
            yield api
    finally:
        app.dependency_overrides.pop(get_demo_repository, None)
        get_settings.cache_clear()


def _ask(client: TestClient, question: str) -> dict:
    response = client.post("/api/v1/patients/PAT-001/ask", json={"question": question})
    assert response.status_code == 200
    return response.json()


def test_unseen_higher_level_renal_concept_expands_to_two_relevant_concepts(client):
    body = _ask(client, "Các chỉ số về chức năng thận đã diễn biến thế nào qua thời gian?")
    answer = body["answer"].casefold()
    assert body["status"] == "answered"
    assert len(body["citations"]) == 8
    assert "creatinine" in answer and "egfr" in answer
    assert "glucose" not in answer and "hba1c" not in answer
    assert "xu hướng" in answer and "→" in answer


def test_unseen_hba1c_trend_is_synthesized_instead_of_dumped(client):
    body = _ask(client, "Diễn tiến HbA1c xuyên suốt các lần đo được ghi nhận ra sao?")
    assert body["status"] == "answered"
    assert len(body["citations"]) == 4
    assert "→" in body["answer"] and "xu hướng" in body["answer"]
    assert "Xét nghiệm:" not in body["answer"]


def test_unseen_medication_history_explains_status_change(client):
    body = _ask(client, "Qua các mốc thời gian, metformin được duy trì hay đổi trạng thái?")
    assert body["status"] == "answered"
    assert len(body["citations"]) == 2
    assert "completed" in body["answer"] and "active" in body["answer"]
    assert "trạng thái thay đổi" in body["answer"]


def test_compatible_same_day_diagnoses_are_not_conflicts():
    def diagnosis(identifier: str, code: str, name: str) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=identifier, fact_type="timeline_condition",
            normalized_value={"statement": f"Chẩn đoán: {name}"},
            source_value={"code": code, "condition": name},
            source_time="2026-06-10T08:00:00+07:00", verification_status="verified",
            citations=[{
                "citation_id": f"cit_{identifier}", "source_type": "canonical_record",
                "source_record_id": identifier, "snippet": name,
            }],
        )
    assert detect_conflicts([
        diagnosis("diag_a", "44054006", "Đái tháo đường type 2"),
        diagnosis("diag_b", "38341003", "Tăng huyết áp"),
    ]) == []
