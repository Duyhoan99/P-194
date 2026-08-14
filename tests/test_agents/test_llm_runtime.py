from __future__ import annotations

from types import SimpleNamespace

from google import genai

from src.agents.adapter import AgentRequestAdapter
from src.agents.contracts import AgentRequest, EvidenceItem, RecordCitation
from src.agents.evidence import ScopedEvidence
from src.agents.generation import compose_atomic_claims, compose_atomic_claims_llm
from src.agents.llm_client import NativeGeminiClient, NullLLMClinicalClient


def _scoped_fact() -> ScopedEvidence:
    item = EvidenceItem(
        evidence_id="ev_1",
        fact_type="timeline_condition",
        normalized_value={"statement": "Chẩn đoán nguồn"},
        source_value={},
        source_time=None,
        verification_status="verified",
        citations=[
            RecordCitation(
                citation_id="cit_1",
                source_type="canonical_record",
                source_record_id="condition_1",
                snippet="Chẩn đoán nguồn",
            )
        ],
    )
    return ScopedEvidence(item=item, origin="structured", patient_id="PAT-001", tenant_id="ten_demo")


class _ContractClient:
    def __init__(self) -> None:
        self.claim_calls = 0
        self.entailment_calls = 0

    def generate_claims(self, question, evidence_packet, *, temperature=0.0):
        self.claim_calls += 1
        assert evidence_packet[0]["evidence_id"] == "ev_1"
        return {
            "claims": [
                {
                    "text": "Diễn đạt từ mô hình",
                    "evidence_ids": ["ev_1"],
                    "section_code": "active_conditions",
                }
            ],
            "unsupported_claims": [],
            "conflicts": [],
        }

    def generate_plan(self, question, *, temperature=0.0):
        return None

    def verify_entailment(self, claim_text, evidence_statements, *, temperature=0.0):
        self.entailment_calls += 1
        return True


def test_configured_runtime_uses_settings_object_without_environment_copy() -> None:
    from src.agents.llm_client import get_llm_runtime

    settings = SimpleNamespace(
        agent_generation_backend="llm",
        llm_api_key="configured-key",
        llm_model_name="gemini-test",
        llm_base_url="",
    )

    runtime = get_llm_runtime(settings)

    assert runtime.available is True
    assert isinstance(runtime.client, NativeGeminiClient)


def test_configured_runtime_is_unavailable_for_disabled_backend_or_missing_key() -> None:
    from src.agents.llm_client import get_llm_runtime

    disabled = get_llm_runtime(
        SimpleNamespace(
            agent_generation_backend="deterministic",
            llm_api_key="configured-key",
            llm_model_name="gemini-test",
            llm_base_url="",
        )
    )
    missing_key = get_llm_runtime(
        SimpleNamespace(
            agent_generation_backend="llm",
            llm_api_key="",
            llm_model_name="gemini-test",
            llm_base_url="",
        )
    )

    assert disabled.available is False
    assert missing_key.available is False
    assert isinstance(disabled.client, NullLLMClinicalClient)
    assert isinstance(missing_key.client, NullLLMClinicalClient)


def test_llm_generation_uses_shared_evidence_packet_keyword() -> None:
    client = _ContractClient()

    result = compose_atomic_claims_llm([_scoped_fact()], client)

    assert client.claim_calls == 1
    assert result["claims"][0].text == "Diễn đạt từ mô hình"
    assert result["claims"][0].text != compose_atomic_claims([_scoped_fact()])[0].text


def test_native_gemini_json_generation_reserves_output_and_bounds_thinking(monkeypatch) -> None:
    captured = {}

    class _Models:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                text='{"claims":[{"text":"Grounded","evidence_ids":["ev_1"],"section_code":"active_conditions"}]}'
            )

    monkeypatch.setattr(genai, "Client", lambda **kwargs: SimpleNamespace(models=_Models()))
    client = NativeGeminiClient(api_key="test-key", model_name="gemini-3.5-flash")

    result = client.generate_claims("question", [{"evidence_id": "ev_1", "statement": "source"}])

    config = captured["config"]
    assert result and result["claims"]
    assert config.max_output_tokens >= 4096
    assert config.thinking_config is not None
    assert config.thinking_config.include_thoughts is False


def test_verifier_delegates_to_configured_shared_client(monkeypatch) -> None:
    from src.agents import verification

    client = _ContractClient()
    runtime = SimpleNamespace(available=True, client=client)
    monkeypatch.setattr(verification, "get_llm_runtime", lambda: runtime, raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    assert verification.verify_entailment_llm("claim", ["evidence"]) is True
    assert client.entailment_calls == 1


def _generation_state() -> dict:
    return {
        "request": AgentRequest(
            request_id="req_generation",
            task_type="ask_chart",
            tenant_id="ten_demo",
            patient_id="PAT-001",
            user_id="doctor_1",
            data_watermark="wm_1",
            profile_versions=[],
            approved_memory=None,
            structured_facts=[],
            note_evidence=[],
            question="Chẩn đoán là gì?",
        ),
        "question_type": {
            "task_type": "clinical_question",
            "retrieval_required": True,
        },
        "retrieved_evidence": [_scoped_fact()],
        "conflicts": [],
    }


def test_generation_node_uses_controlled_available_runtime(monkeypatch) -> None:
    from src.agents.nodes import clinical_nodes

    client = _ContractClient()
    monkeypatch.setattr(
        clinical_nodes,
        "get_llm_runtime",
        lambda: SimpleNamespace(available=True, client=client),
        raising=False,
    )
    monkeypatch.delenv("AGENT_GENERATION_BACKEND", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    result = clinical_nodes.generate_grounded_node(_generation_state())

    assert client.claim_calls == 1
    assert result["proposed_claims"][0].text == "Diễn đạt từ mô hình"


def test_generation_node_falls_back_when_controlled_runtime_unavailable(monkeypatch) -> None:
    from src.agents.nodes import clinical_nodes

    monkeypatch.setattr(
        clinical_nodes,
        "get_llm_runtime",
        lambda: SimpleNamespace(available=False, client=NullLLMClinicalClient()),
        raising=False,
    )

    result = clinical_nodes.generate_grounded_node(_generation_state())

    assert result["proposed_claims"][0].text == "Chẩn đoán nguồn"


def test_adapter_preserves_cited_current_medication_provenance() -> None:
    packet = {
        "patient_id": "PAT-001",
        "data_watermark": "wm_1",
        "timeline": [],
        "lab_trends": {},
        "active_conditions": [],
        "current_medications": [
            {
                "medication": "ExampleMed 10 mg",
                "status": "active",
                "citations": [
                    {
                        "citation_id": "cit_med_1",
                        "source_type": "canonical_record",
                        "source_record_id": "medication_1",
                        "snippet": "ExampleMed 10 mg active",
                    }
                ],
            }
        ],
    }

    request = AgentRequestAdapter().from_evidence_packet(
        packet,
        request_id="req_1",
        task_type="ask_chart",
        tenant_id="ten_demo",
        user_id="doctor_1",
        profile_versions=[],
        question="Thuốc hiện tại là gì?",
    )

    medication = next(fact for fact in request.structured_facts if fact["fact_type"] == "current_medication_backend_fact")
    assert medication["normalized_value"]["statement"] == "Thuốc hiện tại: ExampleMed 10 mg (active)"
    assert medication["citations"][0]["citation_id"] == "cit_med_1"
