from fastapi.testclient import TestClient

from src.agents.contracts import EvidenceItem
from src.agents.retrieval.conflict import detect_conflicts
from src.api.dependencies import get_demo_repository
from src.clinical.demo_repository import DemoRepository
from src.main import app


def _fact(evidence_id: str, fact_type: str, when: str, title: str, summary: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id, fact_type=fact_type,
        normalized_value={"statement": f"{title}: {summary}"},
        source_value={"title": title, "summary": summary}, source_time=when,
        verification_status="verified",
        citations=[{
            "citation_id": f"cit_{evidence_id}", "source_type": "canonical_record",
            "source_record_id": evidence_id, "snippet": summary,
        }],
    )


def test_longitudinal_labs_and_medication_changes_are_not_conflicts():
    facts = [
        _fact("a", "timeline_observation", "2025-01-10", "Xét nghiệm: HbA1c", "Kết quả: 7.1 %"),
        _fact("b", "timeline_observation", "2026-01-10", "Xét nghiệm: HbA1c", "Kết quả: 8.2 %"),
        _fact("c", "timeline_medication", "2025-01-10", "Thuốc: Metformin 500 mg", "active"),
        _fact("d", "timeline_medication", "2026-01-10", "Thuốc: Metformin 1000 mg", "active"),
    ]
    assert detect_conflicts(facts) == []


def test_same_time_incompatible_lab_and_medication_values_are_conflicts():
    facts = [
        _fact("a", "timeline_observation", "2026-06-10T09:00:00Z", "Xét nghiệm: HbA1c", "Kết quả: 7.4 %"),
        _fact("b", "timeline_observation", "2026-06-10T09:05:00Z", "Xét nghiệm: HbA1c", "Kết quả: 9.1 %"),
        _fact("c", "timeline_medication", "2026-06-10T08:00:00Z", "Thuốc: Metformin 500 mg", "active"),
        _fact("d", "timeline_medication", "2026-06-10T08:05:00Z", "Thuốc: Metformin 1000 mg", "active"),
    ]
    assert len(detect_conflicts(facts)) == 2


def test_unseen_comparison_and_conflict_intents_use_exact_api(monkeypatch):
    monkeypatch.setenv("AGENT_GENERATION_BACKEND", "deterministic")
    repo = DemoRepository()
    app.dependency_overrides[get_demo_repository] = lambda: repo
    try:
        with TestClient(app) as client:
            compared = client.post(
                "/api/v1/patients/PAT-001/ask",
                json={"question": "Các chỉ số xét nghiệm thay đổi ra sao so với nửa năm trước?"},
            ).json()
            checked = client.post(
                "/api/v1/patients/PAT-001/ask",
                json={"question": "Có nguồn nào ghi nhận trái ngược nhau không?"},
            ).json()
    finally:
        app.dependency_overrides.pop(get_demo_repository, None)
    assert compared["status"] == "answered"
    assert "→" in compared["answer"]
    assert len(compared["citations"]) >= 2
    assert "Chẩn đoán" not in compared["answer"]
    assert checked["status"] == "answered"
    assert checked["citations"] == []
    assert "Không phát hiện xung đột thực sự" in checked["answer"]
