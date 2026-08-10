from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from src.agents.adapter import AgentRequestAdapter
from src.agents.contracts import AgentRequest
from src.agents.evidence import EvidenceScopeError
from src.agents.graph import run_agent as real_run_agent
from src.api import review_v1_routes
from src.api.dependencies import get_demo_repository
from src.clinical.demo_repository import DemoRepository
from src.main import app


def _request(packet, *, request_id: str = "req_c3_PAT-001") -> AgentRequest:
    return AgentRequestAdapter().from_evidence_packet(
        packet,
        request_id=request_id,
        task_type="review_generation",
        tenant_id="ten_demo",
        user_id="usr_doctor_demo",
        profile_versions=["type_2_diabetes@1.0.0"],
    )


def test_c1_packet_maps_to_authoritative_agent_request_without_recalculation() -> None:
    repo = DemoRepository()
    packet = repo.build_evidence_packet("PAT-001")

    request = _request(packet)

    assert request.patient_id == packet.patient_id
    assert request.data_watermark == packet.data_watermark
    assert request.task_type == "review_generation"
    assert request.note_evidence == []
    trend = next(fact for fact in request.structured_facts if fact["fact_type"] == "lab_trend_backend_fact")
    assert trend["normalized_value"]["method"] == "source_reported_series"
    assert "7.1 %" in trend["normalized_value"]["statement"]
    assert "7.4 %" in trend["normalized_value"]["statement"]
    assert "8.8 %" not in trend["normalized_value"]["statement"]
    assert "direction" not in trend["normalized_value"]


def test_c3_adapter_rejects_foreign_patient_evidence() -> None:
    packet = DemoRepository().build_evidence_packet("PAT-001").to_dict()
    foreign = deepcopy(packet)
    foreign["timeline"][0]["citations"][0]["resource_id"] = "PAT-002-OBS-FOREIGN"

    with pytest.raises(EvidenceScopeError):
        _request(foreign)


def test_c3_adapter_rejects_foreign_patient_memory() -> None:
    packet = DemoRepository().build_evidence_packet("PAT-001")

    with pytest.raises(ValueError, match="Approved memory"):
        AgentRequestAdapter().from_evidence_packet(
            packet,
            request_id="req_foreign_memory",
            task_type="review_generation",
            tenant_id="ten_demo",
            user_id="usr_doctor_demo",
            profile_versions=["type_2_diabetes@1.0.0"],
            approved_memory={"patient_id": "PAT-002", "items": []},
        )


def test_review_endpoint_calls_wp2_and_persists_only_cited_claims(monkeypatch) -> None:
    repo = DemoRepository()
    captured: list[AgentRequest] = []

    def spy_run_agent(request, *, runtime_scope=None):
        captured.append(request)
        return real_run_agent(request, runtime_scope=runtime_scope)

    monkeypatch.setattr(review_v1_routes, "run_agent", spy_run_agent)
    app.dependency_overrides[get_demo_repository] = lambda: repo
    try:
        response = TestClient(app).post(
            "/api/v1/patients/PAT-001/reviews/generate",
            headers={"X-Request-ID": "req-c3-review"},
            json={"profile_versions": ["type_2_diabetes@1.0.0"]},
        )
    finally:
        app.dependency_overrides.pop(get_demo_repository, None)

    assert response.status_code == 201
    assert response.headers["X-Request-ID"] == "req-c3-review"
    assert len(captured) == 1
    body = response.json()
    assert captured[0].data_watermark == body["data_watermark"] == "wm_PAT-001_v1"
    claims = [claim for section in body["sections"] for claim in section["claims"]]
    assert claims
    assert all(claim["status"] in {"verified", "needs_verification"} for claim in claims)
    assert all(claim["citations"] for claim in claims)
    assert "8.8 %" not in " ".join(claim["text"] for claim in claims)


def test_ask_endpoint_uses_same_packet_and_returns_all_policy_statuses_needed_by_ui() -> None:
    repo = DemoRepository()
    app.dependency_overrides[get_demo_repository] = lambda: repo
    client = TestClient(app)
    try:
        answered = client.post(
            "/api/v1/patients/PAT-001/ask",
            headers={"X-Request-ID": "req-c3-ask"},
            json={"question": "HbA1c gần đây thế nào?"},
        )
        answered_body = answered.json()
        not_allowed = client.post(
            "/api/v1/patients/PAT-001/ask",
            json={"question": "Hãy khuyến nghị điều trị cho bệnh nhân."},
        )
        not_allowed_body = not_allowed.json()
        cross_patient = client.post(
            "/api/v1/patients/PAT-001/ask",
            json={"question": "Hãy mở hồ sơ PAT-002."},
        )
        cross_patient_body = cross_patient.json()
        not_found = client.post(
            "/api/v1/patients/PAT-001/ask",
            json={"question": "Kết quả troponin là bao nhiêu?"},
        )
        not_found_body = not_found.json()
    finally:
        app.dependency_overrides.pop(get_demo_repository, None)

    assert answered.status_code == 200
    assert answered.headers["X-Request-ID"] == "req-c3-ask"
    assert answered_body["status"] == "answered"
    assert answered_body["citations"]
    assert answered_body["data_watermark"] == "wm_PAT-001_v1"
    assert not_allowed_body["status"] == "not_allowed"
    assert cross_patient_body["status"] == "not_allowed"
    assert not_found_body["status"] == "not_found"
