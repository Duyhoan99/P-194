from unittest import mock

from src.agents.contracts import EvidenceItem, RecordCitation
from src.agents.evidence import ScopedEvidence
from src.agents.generation import ProposedClaim
from src.agents.verification import verify_claim


def _mock_evidence(eid, stmt, value=None, unit=None, date=None, fact_type="observation"):
    nv = {"statement": stmt}
    if value is not None:
        nv["value"] = value
    if unit is not None:
        nv["unit"] = unit

    citation = RecordCitation(citation_id=eid, source_type="canonical_record", source_record_id=eid, snippet="")

    return ScopedEvidence(
        item=EvidenceItem(
            evidence_id=eid, fact_type=fact_type, normalized_value=nv,
            source_value=stmt, source_time=date, verification_status="verified", citations=[citation]
        ),
        origin="structured", patient_id="p1", tenant_id="t1"
    )

@mock.patch("src.agents.verification.verify_entailment_llm", return_value=True)
def test_paraphrase_accepted(mock_verify):
    e = _mock_evidence("e1", "Metformin 1000 mg active", fact_type="medication", value="1000", unit="mg")
    c = ProposedClaim(claim_id="c1", text="Bệnh nhân hiện đang sử dụng Metformin 1000 mg.", evidence_ids=["e1"], section_code="current_medications")

    verified, res = verify_claim(c, {"e1": e})
    assert res.status == "verified"
    assert res.checks["entailed"] is True

def test_wrong_number_rejected():
    e = _mock_evidence("e1", "HbA1c 7.4 %", value="7.4")
    c = ProposedClaim(claim_id="c2", text="HbA1c của bệnh nhân là 8.4%.", evidence_ids=["e1"], section_code="recent_results")

    verified, res = verify_claim(c, {"e1": e})
    assert res.status == "unsupported"
    assert res.checks["numeric_unit_date_exact"] is False

def test_wrong_unit_rejected():
    e = _mock_evidence("e1", "Glucose 120 mg/dL", value="120", unit="mg/dL")
    c = ProposedClaim(claim_id="c3", text="Glucose 120 mmol/L", evidence_ids=["e1"], section_code="recent_results")

    verified, res = verify_claim(c, {"e1": e})
    assert res.status == "unsupported"
    assert res.checks["numeric_unit_date_exact"] is False

def test_wrong_date_rejected():
    e = _mock_evidence("e1", "HbA1c 7.4%", value="7.4", date="2026-08-01T00:00:00")
    c = ProposedClaim(claim_id="c4", text="HbA1c 7.4% ngày 2026-07-01", evidence_ids=["e1"], section_code="recent_results")

    verified, res = verify_claim(c, {"e1": e})
    assert res.status == "unsupported"
    assert res.checks["numeric_unit_date_exact"] is False

def test_negation_inversion_rejected():
    e = _mock_evidence("e1", "Không ghi nhận dị ứng thuốc")
    e.item.normalized_value["assertion"] = "absent"
    c = ProposedClaim(claim_id="c5", text="Bệnh nhân có dị ứng thuốc", evidence_ids=["e1"], section_code="active_conditions")

    verified, res = verify_claim(c, {"e1": e})
    assert res.status == "unsupported"
    assert res.checks["negation_preserved"] is False

def test_fabricated_citation_rejected():
    e = _mock_evidence("e1", "HbA1c 7.4%")
    c = ProposedClaim(claim_id="c6", text="HbA1c 7.4%", evidence_ids=["fake_999"], section_code="recent_results")

    verified, res = verify_claim(c, {"e1": e})
    assert res.status == "unsupported"
    assert res.checks["evidence_exists"] is False

@mock.patch("src.agents.verification.verify_entailment_llm", return_value=True)
def test_multi_evidence_trend_accepted(mock_verify):
    e1 = _mock_evidence("e1", "HbA1c 8.5%", value="8.5")
    e2 = _mock_evidence("e2", "HbA1c 7.4%", value="7.4")
    c = ProposedClaim(claim_id="c7", text="HbA1c giảm từ 8.5% xuống 7.4%.", evidence_ids=["e1", "e2"], section_code="recent_results")

    verified, res = verify_claim(c, {"e1": e1, "e2": e2})
    assert res.status == "verified"
    assert res.checks["numeric_unit_date_exact"] is True

def test_narrative_semantic_paraphrase_accepted():
    e = _mock_evidence("e1", "Patient frequently misses evening doses.", fact_type="note")
    c = ProposedClaim(claim_id="c8", text="Hồ sơ cho thấy bệnh nhân thường xuyên bỏ lỡ liều buổi tối.", evidence_ids=["e1"], section_code="data_gaps")

    from unittest import mock
    with mock.patch("src.agents.verification.verify_entailment_llm", return_value=True):
        verified, res = verify_claim(c, {"e1": e})
        assert res.checks["entailed"] is True

def test_fabricated_citation_final_output_result():
    from src.agents.contracts import AgentRequest, VerifiedClaim
    from src.agents.nodes.clinical_nodes import finalize_response_node
    from src.agents.state import ClinicalReviewState

    # Simulate state after verification where fake citation resulted in unsupported claim
    c = VerifiedClaim(
        claim_id="c6", text="Fake claim text", status="unsupported",
        confidence="low", citations=[], generator_version="test"
    )

    state = ClinicalReviewState(
        request=AgentRequest(
            task_type="ask_chart", patient_id="p1", tenant_id="t1", question="?",
            approved_memory={}, structured_facts=[], note_evidence=[],
            request_id="req1", user_id="u1", data_watermark="1", profile_versions=[]
        ),
        claims=[],  # NO verified claims
        unsupported_claims=[c],
        status="not_found",
        conflicts=[]
    )

    final_res = finalize_response_node(state)
    result = final_res["public_response"]

    # Fake claim should not be in the final supported answer
    # If there are no verified claims, answer is _NOT_FOUND
    assert result.status == "not_found"
    assert "Fake claim text" not in (result.answer or "")

    # Fake citation should not be in the final citations
    assert len(result.citations) == 0

if __name__ == "__main__":
    test_paraphrase_accepted()
    test_wrong_number_rejected()
    test_wrong_unit_rejected()
    test_wrong_date_rejected()
    test_negation_inversion_rejected()
    test_fabricated_citation_rejected()
    test_multi_evidence_trend_accepted()
    test_narrative_semantic_paraphrase_accepted()
    print("Phase 4 tests passed!")
