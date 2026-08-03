from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.config import get_settings
from src.main import app
from tests.clinical_fixtures import create_mock_clinical_db


def complete_checklist() -> dict[str, bool]:
    return {
        "reviewed_summary": True,
        "checked_critical_evidence": True,
        "understands_ai_limitations": True,
        "confirms_edits": True,
    }


@pytest.mark.asyncio
async def test_doctor_generates_persisted_draft_with_citations(authenticated_client):
    """Skipping durable generation would return uncitable transient clinical content."""
    response = await authenticated_client.post("/api/v1/clinical/patients/101/summaries")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["draft"]["citations"][0]["citation_id"] == "labevent_id=9001"
    assert body["draft"]["trace_id"]


@pytest.mark.asyncio
async def test_assigned_patients_response_has_a_trace_id(authenticated_client):
    """Omitting the trace identifier would make an assigned-patient response unauditable."""
    response = await authenticated_client.get("/api/v1/clinical/patients")

    assert response.status_code == 200
    assert response.json()["patients"] == [101]
    assert response.json()["trace_id"]


@pytest.mark.asyncio
async def test_signed_demo_doctor_uses_server_side_assignment_in_default_retrieval(
    monkeypatch, tmp_path
):
    """Keeping the default fail-closed checker in demo mode would make signed doctors unusable."""
    database_path = tmp_path / "synthetic-clinical.sqlite"
    create_mock_clinical_db(database_path)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CLINICAL_CURSOR_SECRET", "s" * 32)
    monkeypatch.setenv("CLINICAL_DATABASE_PATH", str(database_path))
    get_settings.cache_clear()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/v1/auth/demo-login",
                json={"username": "doctor-1", "password": "demo"},
            )
            response = await client.get("/api/v1/clinical/patients/101/labs")
    finally:
        get_settings.cache_clear()

    assert login.status_code == 204
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_doctor_cannot_generate_summary_for_unassigned_subject(authenticated_client):
    """Trusting a path identifier without assignment enforcement would leak another patient's evidence."""
    response = await authenticated_client.post("/api/v1/clinical/patients/202/summaries")

    assert response.status_code == 403
    assert response.json()["trace_id"]


@pytest.mark.asyncio
async def test_unknown_summary_returns_not_found(authenticated_client):
    """Treating an absent summary as an authorization failure breaks the API's 404 contract."""
    response = await authenticated_client.get(f"/api/v1/clinical/summaries/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["trace_id"]


@pytest.mark.asyncio
async def test_review_action_for_unknown_summary_returns_not_found(authenticated_client):
    """Leaving an unknown review action uncaught would convert a safe 404 into a server error."""
    response = await authenticated_client.post(
        f"/api/v1/clinical/summaries/{uuid4()}/approve",
        json=complete_checklist(),
    )

    assert response.status_code == 404
    assert response.json()["trace_id"]


@pytest.mark.asyncio
async def test_approval_requires_completed_review_checklist(authenticated_client, summary_id):
    """Accepting a partial checklist would approve an unreviewed clinical draft."""
    response = await authenticated_client.post(
        f"/api/v1/clinical/summaries/{summary_id}/approve",
        json={**complete_checklist(), "checked_critical_evidence": False},
    )

    assert response.status_code == 422
    assert response.json()["trace_id"]


@pytest.mark.asyncio
async def test_edit_creates_new_version_and_versions_remain_immutable(authenticated_client, summary_id):
    """Mutating the draft in place would erase the clinician review history."""
    current = await authenticated_client.get(f"/api/v1/clinical/summaries/{summary_id}")
    patch = current.json()["draft"]
    patch["warnings"] = ["Doctor requested revision."]
    response = await authenticated_client.patch(
        f"/api/v1/clinical/summaries/{summary_id}",
        json={"draft": patch, "reason": "Clarify warning"},
    )
    versions = await authenticated_client.get(f"/api/v1/clinical/summaries/{summary_id}/versions")

    assert response.status_code == 200
    assert response.json()["version_number"] == 2
    assert response.json()["status"] == "NEEDS_REVISION"
    assert response.json()["draft"]["trace_id"] != patch["trace_id"]
    assert [version["version_number"] for version in versions.json()] == [1, 2]


@pytest.mark.asyncio
async def test_edit_rejects_client_relabeling_of_scope_and_uses_request_trace(authenticated_client, summary_id):
    """Allowing an edit to relabel its subject, encounter, or trace would corrupt immutable review provenance."""
    current = await authenticated_client.get(f"/api/v1/clinical/summaries/{summary_id}")
    patch = current.json()["draft"]
    patch.update({"subject_id": 202, "hadm_id": 9999, "stay_id": 8888, "trace_id": str(uuid4())})
    response = await authenticated_client.patch(
        f"/api/v1/clinical/summaries/{summary_id}",
        json={"draft": patch, "reason": "Attempt to relabel immutable scope"},
    )
    stored = await authenticated_client.get(f"/api/v1/clinical/summaries/{summary_id}")

    assert response.status_code == 422
    assert stored.json()["draft"]["subject_id"] == 101
    assert stored.json()["draft"]["hadm_id"] is None
    assert stored.json()["draft"]["stay_id"] is None


@pytest.mark.asyncio
async def test_edit_rejects_fabricated_evidence_text_and_lineage(authenticated_client, summary_id):
    """Structural citation IDs alone must not permit fabricated claims to enter an approvable version."""
    current = await authenticated_client.get(f"/api/v1/clinical/summaries/{summary_id}")
    patch = current.json()["draft"]
    patch["sections"]["Laboratory Trends"][0]["text"] = "Fabricated clinical conclusion."
    patch["citations"][0]["lineage"]["subject_id"] = 202
    response = await authenticated_client.patch(
        f"/api/v1/clinical/summaries/{summary_id}",
        json={"draft": patch, "reason": "Attempt to fabricate evidence"},
    )
    versions = await authenticated_client.get(f"/api/v1/clinical/summaries/{summary_id}/versions")

    assert response.status_code == 422
    assert [version["status"] for version in versions.json()] == ["DRAFT"]


@pytest.mark.asyncio
async def test_edit_rejects_claim_without_a_valid_citation(authenticated_client, summary_id):
    """Persisting an uncited edit would make a later approval appear evidence-backed."""
    current = await authenticated_client.get(f"/api/v1/clinical/summaries/{summary_id}")
    patch = current.json()["draft"]
    patch["sections"]["Laboratory Trends"][0]["citation_ids"] = []
    response = await authenticated_client.patch(
        f"/api/v1/clinical/summaries/{summary_id}",
        json={"draft": patch, "reason": "Attempt to remove citation"},
    )

    assert response.status_code == 422
    assert response.json()["trace_id"]


@pytest.mark.asyncio
async def test_repeated_generation_returns_existing_draft_without_duplicate_version(authenticated_client):
    """Reinserting the deterministic summary UUID would turn a harmless regeneration into a server error."""
    first = await authenticated_client.post("/api/v1/clinical/patients/101/summaries")
    second = await authenticated_client.post("/api/v1/clinical/patients/101/summaries")
    versions = await authenticated_client.get(f"/api/v1/clinical/summaries/{first.json()['summary_id']}/versions")

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["summary_id"] == first.json()["summary_id"]
    assert [version["version_number"] for version in versions.json()] == [1]


@pytest.mark.asyncio
async def test_reject_requires_nonempty_reason(authenticated_client, summary_id):
    """A rejection without a reason would leave the next reviewer without a remediation record."""
    response = await authenticated_client.post(
        f"/api/v1/clinical/summaries/{summary_id}/reject",
        json={"reason": "   "},
    )

    assert response.status_code == 422
    assert response.json()["trace_id"]


@pytest.mark.asyncio
async def test_nonapproved_export_is_rejected_by_review_policy(authenticated_client, summary_id):
    """Returning a draft PDF would bypass the existing backend approval gate."""
    response = await authenticated_client.post(f"/api/v1/clinical/summaries/{summary_id}/export")

    assert response.status_code == 409
    assert response.json()["trace_id"]


@pytest.mark.asyncio
async def test_approved_export_returns_pdf_with_trace_header(authenticated_client, summary_id):
    """A successful binary clinical export still needs a correlation identifier."""
    approval = await authenticated_client.post(
        f"/api/v1/clinical/summaries/{summary_id}/approve",
        json=complete_checklist(),
    )
    response = await authenticated_client.post(f"/api/v1/clinical/summaries/{summary_id}/export")

    assert approval.status_code == 200
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-trace-id"]
