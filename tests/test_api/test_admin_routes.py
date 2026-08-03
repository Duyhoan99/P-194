"""Role boundaries for the administrative and compliance HTTP surface."""

import pytest


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
