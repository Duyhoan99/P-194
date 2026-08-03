"""Role and safe-payload boundaries for operations endpoints."""

import pytest


@pytest.mark.asyncio
async def test_operations_status_contains_only_safe_operational_metadata(admin_client):
    """Including a clinical value in status output would expose patient data to operations roles."""
    response = await admin_client.get("/api/v1/ops/clinical-status")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "backend",
        "database",
        "loaded_modules",
        "source_profile",
        "ingestion",
        "llm_gateway",
        "clinical_tools",
        "latency",
        "trace_id",
    }
    assert "raw_value" not in response.text
    assert "1.2" not in response.text
    assert "prompt" not in response.text
    assert "secret" not in response.text.lower()


@pytest.mark.asyncio
async def test_data_steward_can_read_operations_but_not_admin_audit(client, monkeypatch):
    """Letting a data steward read audit metadata would cross the compliance boundary."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CLINICAL_CURSOR_SECRET", "s" * 32)
    login = await client.post(
        "/api/v1/auth/demo-login",
        json={"username": "steward-1", "password": "demo"},
    )
    status = await client.get("/api/v1/ops/clinical-status")
    runs = await client.get("/api/v1/ops/ingestion-runs")
    audit = await client.get("/api/v1/admin/audit")

    assert login.status_code == 204
    assert status.status_code == 200
    assert runs.status_code == 200
    assert audit.status_code == 403
    assert all("raw_row" not in run for run in runs.json()["runs"])


@pytest.mark.asyncio
async def test_doctor_cannot_read_operations_even_with_steward_header(authenticated_client):
    """Trusting a data steward header would disclose system posture to clinicians."""
    response = await authenticated_client.get(
        "/api/v1/ops/ingestion-runs", headers={"X-Role": "DATA_STEWARD"}
    )

    assert response.status_code == 403
    assert "trace_id" in response.json()
