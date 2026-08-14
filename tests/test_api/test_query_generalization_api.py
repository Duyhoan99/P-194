"""Behavioral API regressions for Vietnamese query generalization.

The hold-out wording in this module is intentionally absent from production
rules and lower-level tests.  These tests exercise the same endpoint used by
the UI while keeping all retrieval and planner calls local and deterministic.
"""

from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.agents.retrieval.router import QueryPlanner
from src.api.dependencies import get_demo_repository
from src.clinical.demo_repository import DemoRepository
from src.config import get_settings
from src.main import app

ASK_PATH = "/api/v1/patients/PAT-001/ask"
EXPECTED_WATERMARK = "wm_PAT-001_v1"
PATIENT_TOKEN = re.compile(r"PAT-?\d{3}", re.IGNORECASE)

DIAGNOSIS_REGRESSIONS = (
    "bệnh gì",
    "bệnh nhân bị bệnh gì",
    "bệnh nhân mắc bệnh gì",
    "chẩn đoán của bệnh nhân?",
)

SUMMARY_REGRESSIONS = (
    "tóm tắt",
    "tóm tắt hồ sơ",
    "tổng quan bệnh nhân",
)

# These strings are deliberate API-level hold-outs.  Keep them in this file.
DIAGNOSIS_HOLD_OUTS = (
    "Người bệnh hiện đang mang những chẩn đoán nào?",
    "Hồ sơ này ghi nhận các bệnh lý nào?",
    "Các vấn đề sức khỏe đã được xác định là gì?",
    "Cho biết những tình trạng bệnh đang được theo dõi.",
    "Hiện tại người này được xác nhận mắc những bệnh nào?",
)

SUMMARY_HOLD_OUTS = (
    "Xin điểm lại các thông tin y khoa chính trong hồ sơ này.",
    "Có thể cho tôi cái nhìn tổng quan về diễn biến sức khỏe không?",
    "Hãy gom các dữ kiện lâm sàng quan trọng thành một bản ngắn gọn.",
    "Tôi cần bản khái quát những vấn đề sức khỏe nổi bật.",
    "Tổng hợp giúp tôi các thông tin đáng chú ý trong bệnh án này.",
)

AMBIGUOUS_LLM_QUERY = "Cho tôi biết bức tranh hiện tại của ca này."
AMBIGUOUS_FALLBACK_QUERY = "Xem giúp tôi tình hình của ca này."


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch):
    """Use a fresh repository and forbid external semantic retrieval."""
    monkeypatch.setenv("AGENT_GENERATION_BACKEND", "deterministic")
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()
    repository = DemoRepository()
    app.dependency_overrides[get_demo_repository] = lambda: repository
    monkeypatch.setattr(
        "src.agents.retrieval.vector.SemanticRetriever.retrieve",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        "src.agents.nodes.clinical_nodes.get_llm_runtime",
        lambda: SimpleNamespace(available=False, client=None),
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_demo_repository, None)
        get_settings.cache_clear()


def _ask(client: TestClient, question: str) -> dict:
    response = client.post(ASK_PATH, json={"question": question})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"answered", "conflicting"}
    assert body["data_watermark"] == EXPECTED_WATERMARK
    assert body["answer"].strip()
    assert body["citations"]
    _assert_patient_scoped(body)
    return body


def _assert_patient_scoped(body: dict) -> None:
    """Every patient identifier exposed by grounded output stays PAT-001."""
    exposed = [body.get("answer", ""), json.dumps(body.get("citations", []), ensure_ascii=False)]
    patient_ids = {
        token.upper().replace("PAT", "PAT-").replace("--", "-")
        for value in exposed
        for token in PATIENT_TOKEN.findall(value)
    }
    assert patient_ids <= {"PAT-001"}


@pytest.mark.parametrize("question", DIAGNOSIS_REGRESSIONS)
def test_diagnosis_regressions_return_grounded_patient_scoped_evidence(
    api_client: TestClient, question: str
) -> None:
    _ask(api_client, question)


@pytest.mark.parametrize("question", SUMMARY_REGRESSIONS)
def test_summary_regressions_return_grounded_patient_scoped_evidence(
    api_client: TestClient, question: str
) -> None:
    _ask(api_client, question)


@pytest.mark.parametrize("question", DIAGNOSIS_HOLD_OUTS)
def test_unseen_diagnosis_paraphrases_generalize_at_the_api_boundary(
    api_client: TestClient, question: str
) -> None:
    _ask(api_client, question)


@pytest.mark.parametrize("question", SUMMARY_HOLD_OUTS)
def test_unseen_summary_paraphrases_generalize_at_the_api_boundary(
    api_client: TestClient, question: str
) -> None:
    _ask(api_client, question)


def test_minimal_diagnosis_query_remains_grounded(api_client: TestClient) -> None:
    _ask(api_client, "bệnh")


def test_greeting_remains_answered_without_clinical_citations(api_client: TestClient) -> None:
    response = api_client.post(ASK_PATH, json={"question": "xin chào"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["answer"].strip()
    assert body["citations"] == []
    assert body["data_watermark"] == EXPECTED_WATERMARK
    _assert_patient_scoped(body)


@pytest.mark.parametrize("question", ["bye", "???"])
def test_nonclinical_short_messages_never_dump_patient_evidence(
    api_client: TestClient, question: str
) -> None:
    response = api_client.post(ASK_PATH, json={"question": question})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["citations"] == []
    assert "CONFLICTING EVIDENCE" not in body["answer"]


class _PlannerClient:
    def __init__(self, plan: dict | None = None, error: Exception | None = None):
        self.plan = plan
        self.error = error
        self.questions: list[str] = []

    def generate_plan(self, question: str, *, temperature: float = 0.0) -> dict | None:
        del temperature
        self.questions.append(question)
        if self.error is not None:
            raise self.error
        return self.plan


def test_available_llm_planner_can_ground_an_ambiguous_natural_query(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    planner = _PlannerClient(
        plan={
            "task_type": "summary",
            "needs": [{"domain": "all", "temporal": {"intent": "none"}}],
            "use_structured": True,
            "use_semantic": False,
            "use_lexical": False,
            "retrieval_required": True,
        }
    )
    runtime = SimpleNamespace(available=True, client=planner)
    monkeypatch.setattr("src.agents.retrieval.router.get_llm_runtime", lambda: runtime)

    _ask(api_client, AMBIGUOUS_LLM_QUERY)

    assert planner.questions == [AMBIGUOUS_LLM_QUERY]


@pytest.mark.parametrize("mode", ["unavailable", "failure"])
def test_llm_planner_outage_uses_bounded_mixed_fallback_instead_of_not_found(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    if mode == "failure":
        planner = _PlannerClient(error=TimeoutError("controlled planner outage"))
        runtime = SimpleNamespace(available=True, client=planner)
    else:
        planner = _PlannerClient()
        runtime = SimpleNamespace(available=False, client=planner)
    monkeypatch.setattr("src.agents.retrieval.router.get_llm_runtime", lambda: runtime)

    fallback = QueryPlanner().plan(AMBIGUOUS_FALLBACK_QUERY)
    assert fallback.route == "MIXED"
    assert fallback.needs[0].domain == "all"
    assert fallback.use_structured is True
    assert fallback.use_semantic is True
    assert fallback.use_lexical is True
    planner.questions.clear()

    body = _ask(api_client, AMBIGUOUS_FALLBACK_QUERY)

    assert body["status"] != "not_found"
    if mode == "failure":
        assert planner.questions == [AMBIGUOUS_FALLBACK_QUERY]
    else:
        assert planner.questions == []
