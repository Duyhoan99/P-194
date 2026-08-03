"""Role boundaries for the administrative and compliance HTTP surface."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_clinical_service, get_operational_store, get_summary_repository
from src.clinical.operations import OperationalStore
from src.config import get_settings
from src.main import app


@pytest.mark.asyncio
async def test_doctor_cannot_manage_assignments_even_with_role_header(authenticated_client):
    """Trusting a request role header would let a doctor self-elevate to admin."""
    response = await authenticated_client.post(
        "/api/v1/admin/users/doctor-2/assignments",
        json={"subject_id": 101},
        headers={"X-Role": "ADMIN", "X-User-Id": "admin-1"},
    )

    assert response.status_code == 403
    assert "trace_id" in response.json()


@pytest.mark.asyncio
async def test_admin_assignment_revocation_is_audited_with_safe_metadata(admin_client):
    """A revoked assignment without an audit event would make governance changes untraceable."""
    assigned = await admin_client.post(
        "/api/v1/admin/users/doctor-2/assignments", json={"subject_id": 101}
    )
    revoked = await admin_client.delete("/api/v1/admin/users/doctor-2/assignments/101")
    audit = await admin_client.get("/api/v1/admin/audit?action=REVOKE_CLINICAL_SUBJECT")

    assert assigned.status_code == 200
    assert revoked.status_code == 200
    assert audit.status_code == 200
    event = audit.json()["events"][-1]
    assert event == {
        "actor": "admin-1",
        "action": "REVOKE_CLINICAL_SUBJECT",
        "subject_reference": "subject-101",
        "timestamp": event["timestamp"],
        "result": "SUCCESS",
        "trace_id": event["trace_id"],
    }
    assert "raw_value" not in audit.text
    assert "prompt" not in audit.text


@pytest.mark.asyncio
async def test_compliance_can_read_audit_but_cannot_change_assignments(client, monkeypatch):
    """Giving compliance mutation access would violate its append-only oversight role."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CLINICAL_CURSOR_SECRET", "s" * 32)
    login = await client.post(
        "/api/v1/auth/demo-login",
        json={"username": "compliance-1", "password": "demo"},
    )
    audit = await client.get("/api/v1/admin/audit")
    mutation = await client.post(
        "/api/v1/admin/users/doctor-1/assignments", json={"subject_id": 101}
    )

    assert login.status_code == 204
    assert audit.status_code == 200
    assert mutation.status_code == 403


@pytest.mark.asyncio
async def test_signed_doctor_session_reads_assignments_from_the_server_registry(client, admin_client, monkeypatch):
    """Embedding assignments in a login token would leave the dashboard stale after an admin grant."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CLINICAL_CURSOR_SECRET", "s" * 32)
    doctor_login = await client.post(
        "/api/v1/auth/demo-login", json={"username": "doctor-2", "password": "demo"}
    )
    grant = await admin_client.post(
        "/api/v1/admin/users/doctor-2/assignments", json={"subject_id": 101}
    )
    try:
        assigned = await client.get("/api/v1/clinical/patients")
    finally:
        revoke = await admin_client.delete("/api/v1/admin/users/doctor-2/assignments/101")
    revoked = await client.get("/api/v1/clinical/patients")

    assert doctor_login.status_code == 204
    assert grant.status_code == 200
    assert assigned.json()["patients"] == [101]
    assert revoke.status_code == 200
    assert revoked.json()["patients"] == []


class FailingAuditStore(OperationalStore):
    """Exercises the route boundary when the mandatory audit write cannot persist."""

    def record(self, event):
        del event
        raise RuntimeError("audit sink unavailable")


@pytest.mark.asyncio
async def test_assignment_change_rolls_back_when_required_audit_write_fails(monkeypatch):
    """Leaving the assignment changed after a failed audit write would create an untraceable grant."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CLINICAL_CURSOR_SECRET", "s" * 32)
    get_settings.cache_clear()
    store = FailingAuditStore()
    app.dependency_overrides[get_operational_store] = lambda: store
    transport = ASGITransport(app, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/v1/auth/demo-login", json={"username": "admin-1", "password": "demo"}
            )
            response = await client.post(
                "/api/v1/admin/users/doctor-2/assignments", json={"subject_id": 101}
            )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert login.status_code == 204
    assert response.status_code == 503
    assert store.get_user("doctor-2").assigned_subject_ids == set()


@pytest.mark.asyncio
async def test_compliance_audit_includes_generation_and_review_events(
    client, monkeypatch, fake_service, summary_repository
):
    """A separate operational sink would hide the existing clinical summary trail from compliance."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CLINICAL_CURSOR_SECRET", "s" * 32)
    get_settings.cache_clear()
    app.dependency_overrides[get_clinical_service] = lambda: fake_service
    app.dependency_overrides[get_summary_repository] = lambda: summary_repository
    try:
        doctor_login = await client.post(
            "/api/v1/auth/demo-login", json={"username": "doctor-1", "password": "demo"}
        )
        generated = await client.post("/api/v1/clinical/patients/101/summaries")
        approved = await client.post(
            f"/api/v1/clinical/summaries/{generated.json()['summary_id']}/approve",
            json={
                "reviewed_summary": True,
                "checked_critical_evidence": True,
                "understands_ai_limitations": True,
                "confirms_edits": True,
            },
        )
        await client.post("/api/v1/auth/logout")
        compliance_login = await client.post(
            "/api/v1/auth/demo-login", json={"username": "compliance-1", "password": "demo"}
        )
        audit = await client.get("/api/v1/admin/audit")
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    actions = {event["action"] for event in audit.json()["events"]}
    assert doctor_login.status_code == 204
    assert generated.status_code == 201
    assert approved.status_code == 200
    assert compliance_login.status_code == 204
    assert {"GENERATE_CLINICAL_SUMMARY", "APPROVE_CLINICAL_SUMMARY"} <= actions
    assert "raw_value" not in audit.text
    assert "prompt" not in audit.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("from_time", "2026-08-03T00:00:00"),
        ("to_time", "not-an-iso-datetime"),
    ],
)
async def test_audit_rejects_naive_or_malformed_time_filters_with_trace(parameter, value, monkeypatch):
    """Comparing a client-naive time to UTC audit events must not escape as a 500."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CLINICAL_CURSOR_SECRET", "s" * 32)
    get_settings.cache_clear()
    transport = ASGITransport(app, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/v1/auth/demo-login", json={"username": "admin-1", "password": "demo"}
            )
            grant = await client.post(
                "/api/v1/admin/users/doctor-2/assignments", json={"subject_id": 101}
            )
            response = await client.get("/api/v1/admin/audit", params={parameter: value})
            await client.delete("/api/v1/admin/users/doctor-2/assignments/101")
    finally:
        get_settings.cache_clear()

    assert login.status_code == 204
    assert grant.status_code == 200
    assert response.status_code == 422
    assert response.json()["trace_id"]
    assert "not-an-iso-datetime" not in response.text
