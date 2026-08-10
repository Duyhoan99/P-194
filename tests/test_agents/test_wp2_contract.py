import json
from pathlib import Path

from src.agents.contracts import AgentRequest, AgentResult
from src.agents.graph import run_agent

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "eval" / "fixtures" / "agent_requests"


def load_request(name: str) -> AgentRequest:
    return AgentRequest.model_validate_json((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def test_all_agent_request_fixtures_match_contract() -> None:
    paths = sorted(FIXTURES.glob("*.json"))
    assert len(paths) >= 12
    for path in paths:
        request = AgentRequest.model_validate_json(path.read_text(encoding="utf-8"))
        assert request.patient_id.startswith("PAT-")
        assert request.data_watermark


def test_answered_result_preserves_watermark_and_gold_citations() -> None:
    request = load_request("answered_hba1c")
    result = run_agent(request)

    assert result.status == "answered"
    assert result.data_watermark == request.data_watermark
    assert {citation.citation_id for citation in result.citations} == {
        "PAT-001-OBS-01-01",
        "PAT-001-OBS-03-01",
        "PAT-001-OBS-04-01",
    }
    AgentResult.model_validate(result.model_dump(mode="json"))


def test_result_does_not_expose_internal_graph_state() -> None:
    public = run_agent(load_request("answered_hba1c")).model_dump(mode="json")
    forbidden = {
        "question_type",
        "evidence_packet",
        "retrieved_evidence",
        "proposed_claims",
        "verification_results",
        "runtime_scope",
        "analysis",
        "reasoning",
        "prompt",
        "tool_trace",
    }
    assert forbidden.isdisjoint(public)
    serialized = json.dumps(public, ensure_ascii=False)
    assert all(field not in serialized for field in forbidden)


def test_review_generation_returns_contract_sections_with_citations() -> None:
    result = run_agent(load_request("review_generation"))
    assert result.status == "answered"
    assert result.sections
    assert {section.section_code for section in result.sections} == {
        "active_conditions",
        "recent_results",
    }
    assert all(claim.citations for section in result.sections for claim in section.claims)
