from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_access_context, get_clinical_service
from src.clinical.errors import (
    ClinicalAccessDenied,
    ClinicalDatabaseUnavailable,
    ClinicalQueryTimeout,
)
from src.clinical.schemas import AccessContext
from src.main import app
from tests.test_clinical.conftest import TEST_TRACE_ID, allowed_context

pytest_plugins = ("tests.test_clinical.conftest",)


@pytest_asyncio.fixture
async def authenticated_client(fake_service):
    """Use the shared synthetic clinical service instead of a local database."""
    app.dependency_overrides[get_clinical_service] = lambda: fake_service
    app.dependency_overrides[get_access_context] = allowed_context
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_clinical_route_requires_auth_and_returns_trace(client):
    """Removing the fail-closed access dependency would expose the default database path."""
    response = await client.get("/api/v1/clinical/patients/101/labs")

    assert response.status_code == 503
    assert UUID(response.json()["trace_id"]).version == 4


@pytest.mark.asyncio
async def test_clinical_route_rejects_invalid_scope(authenticated_client, fake_service):
    """Skipping scope validation would let an unrelated admission reach the lab retrieval."""
    fake_service._repository.scope_is_valid = False
    response = await authenticated_client.get(
        "/api/v1/clinical/patients/101/labs?hadm_id=999999"
    )

    assert response.status_code == 422
    assert response.json()["trace_id"] == TEST_TRACE_ID


@pytest.mark.asyncio
async def test_clinical_route_returns_lineage(authenticated_client):
    """Serializing records without provenance would make returned lab evidence unverifiable."""
    response = await authenticated_client.get("/api/v1/clinical/patients/101/labs?limit=1")

    assert response.status_code == 200
    body = response.json()
    assert body["records"][0]["lineage"]["table"] == "labevents"
    assert body["trace_id"] == TEST_TRACE_ID


@pytest.mark.asyncio
async def test_clinical_route_maps_denied_service_response_to_forbidden(authenticated_client, fake_service):
    """Returning a denied clinical response as 200 would conceal an authorization failure."""
    app.dependency_overrides[get_access_context] = lambda: AccessContext(
        user_id="doctor-1",
        role="DOCTOR",
        assigned_subject_ids=set(),
        trace_id=TEST_TRACE_ID,
    )

    response = await authenticated_client.get("/api/v1/clinical/patients/101/labs")

    assert response.status_code == 403
    assert response.json()["trace_id"] == TEST_TRACE_ID


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (ClinicalAccessDenied(), 403),
        (ClinicalDatabaseUnavailable(), 503),
        (ClinicalQueryTimeout(), 504),
    ],
)
async def test_clinical_route_maps_service_errors_to_safe_statuses(
    authenticated_client, error, status_code
):
    """Changing any domain-error mapping must fail instead of leaking a 500 response."""

    class FailingLaboratoryService:
        def get_laboratory_results(self, context, query):
            raise error

    app.dependency_overrides[get_clinical_service] = FailingLaboratoryService
    response = await authenticated_client.get("/api/v1/clinical/patients/101/labs")

    assert response.status_code == status_code
    assert response.json()["trace_id"] == TEST_TRACE_ID


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "expected_fetch"),
    [
        ("/api/v1/clinical/patients/101", "fetch_patient_overview"),
        ("/api/v1/clinical/patients/101/timeline", "fetch_encounter_timeline"),
        (
            "/api/v1/clinical/patients/101/diagnoses-procedures",
            "fetch_diagnoses_and_procedures",
        ),
        ("/api/v1/clinical/patients/101/labs", "fetch_laboratory_results"),
        ("/api/v1/clinical/patients/101/microbiology", "fetch_microbiology_results"),
        ("/api/v1/clinical/patients/101/icu-events", "fetch_icu_events"),
    ],
)
async def test_clinical_routes_delegate_to_one_domain_service_method(
    authenticated_client, fake_service, path, expected_fetch
):
    """Routing a clinical endpoint to a different domain would return the wrong evidence."""
    response = await authenticated_client.get(path)

    assert response.status_code == 200
    assert fake_service._repository.fetch_calls == [expected_fetch]
