from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import (
    get_clinical_service,
    get_review_service,
    get_summary_repository,
    get_summary_service,
)
from src.clinical.access import DemoAssignmentProvider
from src.clinical.review import ReviewService
from src.clinical.summary_repository import SQLiteSummaryRepository
from src.clinical.summary_service import ClinicalSummaryService
from src.config import get_settings
from src.main import app

pytest_plugins = ("tests.test_clinical.conftest",)


@pytest.fixture
def summary_repository(tmp_path: Path) -> SQLiteSummaryRepository:
    return SQLiteSummaryRepository(tmp_path / "clinical-summary-application.sqlite")


@pytest_asyncio.fixture
async def authenticated_client(monkeypatch, fake_service, summary_repository):
    """A demo doctor session backed by the real route and review services."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CLINICAL_CURSOR_SECRET", "s" * 32)
    get_settings.cache_clear()
    assignments = DemoAssignmentProvider({"doctor-1": {101}}, {"admin-1"})
    summary_service = ClinicalSummaryService(fake_service, audit_sink=summary_repository)
    review_service = ReviewService(summary_repository, assignments, summary_repository, summary_service)
    app.dependency_overrides[get_clinical_service] = lambda: fake_service
    app.dependency_overrides[get_summary_repository] = lambda: summary_repository
    app.dependency_overrides[get_summary_service] = lambda: summary_service
    app.dependency_overrides[get_review_service] = lambda: review_service
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/v1/auth/demo-login",
                json={"username": "doctor-1", "password": "demo"},
            )
            assert login.status_code == 204
            yield client
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest_asyncio.fixture
async def admin_client(monkeypatch, fake_service, summary_repository):
    """A demo administrator session for authorization boundary tests."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CLINICAL_CURSOR_SECRET", "s" * 32)
    get_settings.cache_clear()
    assignments = DemoAssignmentProvider({"doctor-1": {101}}, {"admin-1"})
    app.dependency_overrides[get_clinical_service] = lambda: fake_service
    app.dependency_overrides[get_summary_repository] = lambda: summary_repository
    summary_service = ClinicalSummaryService(fake_service, audit_sink=summary_repository)
    app.dependency_overrides[get_summary_service] = lambda: summary_service
    app.dependency_overrides[get_review_service] = lambda: ReviewService(
        summary_repository, assignments, summary_repository, summary_service
    )
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/v1/auth/demo-login",
                json={"username": "admin-1", "password": "demo"},
            )
            assert login.status_code == 204
            yield client
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest_asyncio.fixture
async def summary_id(authenticated_client):
    response = await authenticated_client.post("/api/v1/clinical/patients/101/summaries")
    assert response.status_code == 201
    return response.json()["summary_id"]
