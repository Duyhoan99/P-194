import pytest

from src.api.dependencies import get_summary_generator, get_summary_service
from src.clinical.agent import ClinicalAgent
from src.clinical.errors import ClinicalAgentUnavailable
from src.clinical.summary_service import ClinicalSummaryService
from src.config import get_settings
from src.main import app


class UnavailableAgent:
    def run(self, context, query):
        raise ClinicalAgentUnavailable("Structured summary generation failed safely.")


def test_settings_select_langgraph_summary_backend(monkeypatch):
    monkeypatch.setenv("SUMMARY_AGENT_BACKEND", "langgraph")
    get_settings.cache_clear()

    try:
        assert get_settings().summary_agent_backend == "langgraph"
    finally:
        get_settings.cache_clear()


def test_summary_generator_builds_langgraph_agent(monkeypatch, assigned_service):
    monkeypatch.setenv("SUMMARY_AGENT_BACKEND", "langgraph")
    get_settings.cache_clear()
    monkeypatch.setattr("src.api.dependencies.get_structured_llm", lambda: object())

    try:
        generator = get_summary_generator(assigned_service)
    finally:
        get_settings.cache_clear()

    assert isinstance(generator, ClinicalAgent)
    assert generator._fallback_generator is not None


def test_summary_generator_keeps_demo_available_without_llm_configuration(monkeypatch, assigned_service):
    monkeypatch.setenv("SUMMARY_AGENT_BACKEND", "langgraph")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "src.api.dependencies.get_structured_llm",
        lambda: (_ for _ in ()).throw(RuntimeError("missing API key")),
    )

    try:
        generator = get_summary_generator(assigned_service)
    finally:
        get_settings.cache_clear()

    assert isinstance(generator, ClinicalAgent)
    assert generator._fallback_generator is not None


@pytest.mark.asyncio
async def test_agent_failure_returns_safe_503_without_persisting(
    authenticated_client, fake_service, summary_repository
):
    app.dependency_overrides[get_summary_service] = lambda: ClinicalSummaryService(
        fake_service,
        generator=UnavailableAgent(),
        audit_sink=summary_repository,
    )

    response = await authenticated_client.post("/api/v1/clinical/patients/101/summaries")

    assert response.status_code == 503
    assert response.json()["detail"] == "Clinical summary generation is currently unavailable."
    assert response.json()["trace_id"]
    assert summary_repository.get_latest_for_subject(101) is None
