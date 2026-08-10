from src.agents.evidence import build_scoped_evidence
from src.agents.generation import ProposedClaim
from src.agents.graph import run_agent
from src.agents.memory import MemoryPolicyError, project_approved_memory
from src.agents.verification import verify_claim

from .test_wp2_contract import load_request


def test_egfr_uses_source_reported_backend_fact() -> None:
    request = load_request("answered_egfr")
    fact = request.structured_facts[0]["normalized_value"]
    result = run_agent(request)
    assert fact["method"] == "source_reported"
    assert "nguồn báo cáo" in (result.answer or "")
    assert {citation.citation_id for citation in result.citations} == {
        "PAT-002-OBS-01-06",
        "PAT-002-OBS-03-06",
    }


def test_medication_conflict_keeps_both_sources() -> None:
    result = run_agent(load_request("conflicting_medication"))
    assert result.status == "conflicting"
    assert result.claims[0].status == "needs_verification"
    assert {citation.citation_id for citation in result.citations} == {
        "PAT-003-MED-001",
        "DOC-PAT003-RX-001",
    }


def test_negation_is_preserved_as_absent() -> None:
    result = run_agent(load_request("answered_negation"))
    assert result.status == "answered"
    assert "không đau ngực" in (result.answer or "").casefold()
    assert "có đau ngực" not in (result.answer or "").casefold()


def test_missing_hba1c_abstains_with_scoped_message() -> None:
    result = run_agent(load_request("not_found_hba1c"))
    assert result.status == "not_found"
    assert result.answer == "Không tìm thấy thông tin này trong dữ liệu được cung cấp."
    assert result.claims == []


def test_low_confidence_ocr_is_not_verified() -> None:
    result = run_agent(load_request("needs_verification_ocr"))
    assert result.status == "conflicting"
    assert [claim.status for claim in result.claims] == ["needs_verification"]
    assert result.citations[0].ocr_confidence == 0.42


def test_prompt_injection_is_treated_as_data_and_not_echoed() -> None:
    result = run_agent(load_request("prompt_injection"))
    serialized = result.model_dump_json().casefold()
    assert result.status == "not_found"
    assert "system prompt" not in serialized
    assert "bỏ qua hướng dẫn" not in serialized


def test_entered_in_error_is_excluded() -> None:
    result = run_agent(load_request("entered_in_error"))
    assert result.status == "not_found"
    assert "9.9" not in result.model_dump_json()


def test_mixed_units_only_uses_backend_canonical_fact() -> None:
    request = load_request("answered_mixed_units")
    fact = request.structured_facts[0]["normalized_value"]
    result = run_agent(request)
    assert fact["calculation_version"] == "backend-normalization@1.0.0"
    assert "10.0 mmol/L" in (result.answer or "")
    assert "180 mg/dL" in (result.answer or "")


def test_cross_patient_evidence_fails_closed() -> None:
    result = run_agent(load_request("error_cross_patient"))
    assert result.status == "error"
    assert result.errors[0].code == "EVIDENCE_SCOPE_INVALID"
    assert result.claims == []


def test_cross_patient_question_and_treatment_are_not_allowed() -> None:
    assert run_agent(load_request("not_allowed_cross_patient_token")).status == "not_allowed"
    assert run_agent(load_request("not_allowed_treatment")).status == "not_allowed"


def test_unsupported_claim_is_removed_by_verifier() -> None:
    request = load_request("answered_hba1c")
    evidence = build_scoped_evidence(request)[0]
    proposed = ProposedClaim(
        claim_id="clm_unsupported",
        text="Bệnh nhân nên bắt đầu insulin ngay.",
        evidence_ids=[evidence.item.evidence_id],
        section_code="changes_to_review",
    )
    claim, verification = verify_claim(proposed, {evidence.item.evidence_id: evidence})
    assert claim is None
    assert verification.status == "unsupported"
    assert not verification.checks["entailed"]


def test_memory_policy_is_approved_only_and_verified_only() -> None:
    review = run_agent(load_request("review_generation"))
    try:
        project_approved_memory(
            review_status="generated",
            patient_id="PAT-001",
            review_version_id="rv_generated",
            approved_by=None,
            approved_at=None,
            sections=review.sections or [],
        )
    except MemoryPolicyError:
        pass
    else:
        raise AssertionError("generated review must not produce patient memory")

    memory = project_approved_memory(
        review_status="approved",
        patient_id="PAT-001",
        review_version_id="rv_approved",
        approved_by="clinician_demo",
        approved_at="2026-08-10T12:00:00+07:00",
        sections=review.sections or [],
    )
    assert memory["patient_id"] == "PAT-001"
    assert memory["items"]
    assert {item["section_code"] for item in memory["items"]} == {"active_conditions"}
