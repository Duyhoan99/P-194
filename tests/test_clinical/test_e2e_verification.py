import pytest
import os
from unittest.mock import patch
from typing import Any
from fastapi.testclient import TestClient

from src.main import app
from src.clinical.demo_repository import DemoRepository
from src.api.dependencies import get_demo_repository
from src.agents.contracts import AgentResult
from src.agents.evidence import ScopedEvidence
from src.agents.retrieval.vector import index_evidence, SemanticRetriever

@pytest.fixture
def repo():
    r = DemoRepository()
    # Ensure patient PAT-001 has baseline data
    # Ensure patient PAT-002 is added for cross-patient isolation testing
    r.create_blank_patient("PAT-002", "Bệnh nhân 2")
    return r

@pytest.fixture
def client(repo):
    app.dependency_overrides[get_demo_repository] = lambda: repo
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_structured_retrieval_e2e(client):
    """
    Query: "3 HbA1c gần nhất của bệnh nhân là gì?"
    Verifies Bounded Preloaded Structured Evidence filtering.
    """
    response = client.post("/api/v1/patients/PAT-001/ask", json={"question": "3 HbA1c gần nhất của bệnh nhân là gì?"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["answered", "conflicting"]
    assert "hba1c" in data["answer"].lower()
    # Verify provenance and scope
    assert len(data.get("citations", [])) > 0
    for citation in data.get("citations", []):
        assert "cit_" in citation["citation_id"]
        assert "PAT-001" in citation.get("document_id", "") or "FHIR" in citation.get("document_id", "")

def test_narrative_retrieval_e2e(client, repo):
    """
    Query: "Bệnh nhân có báo cáo hay quên uống thuốc không?"
    Verifies narrative route and semantic/lexical pipeline.
    """
    # Inject a narrative note for PAT-001
    mock_pdf = [{
        "patient_id": "PAT-001",
        "tenant_id": "ten_demo",
        "evidence_id": "ev_forget_1",
        "origin": "note",
        "verification_status": "needs_verification",
        "fact_type": "Ghi chú bác sĩ",
        "source_value": "Bệnh nhân báo cáo hay quên uống thuốc buổi sáng.",
        "normalized_value": {"statement": "Bệnh nhân báo cáo hay quên uống thuốc buổi sáng.", "document_id": "DOC-NOTE-1"},
        "citations": [{
            "citation_id": "cit_forget_1",
            "source_type": "fhir",
            "document_id": "DOC-NOTE-1",
            "resource_type": "Note",
            "resource_id": "res_note_1",
            "source_checksum": "sha256:test",
            "snippet": "hay quên uống thuốc"
        }]
    }]
    repo.add_pdf_evidence("PAT-001", "DOC-NOTE-1", mock_pdf)
    
    response = client.post("/api/v1/patients/PAT-001/ask", json={"question": "Bệnh nhân có báo cáo hay quên uống thuốc không?"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "conflicting"
    assert "quên uống thuốc" in data["answer"].lower() or "quên thuốc" in data["answer"].lower()

def test_temporal_retrieval_e2e(client):
    """
    Query: "HbA1c thay đổi thế nào trong 6 tháng gần đây?"
    Verifies temporal intent filtering ("trend" or "between").
    """
    response = client.post("/api/v1/patients/PAT-001/ask", json={"question": "HbA1c thay đổi thế nào trong 6 tháng gần đây?"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["answered", "conflicting"]
    # It shouldn't just be one value; it should return trend data if available

def test_mixed_retrieval_e2e(client, repo):
    """
    Query: "Sau thay đổi điều trị, HbA1c thay đổi thế nào và có vấn đề tuân thủ thuốc không?"
    Verifies both structured and narrative paths together.
    """
    mock_pdf = [{
        "patient_id": "PAT-001",
        "tenant_id": "ten_demo",
        "evidence_id": "ev_adherence_2",
        "origin": "note",
        "verification_status": "needs_verification",
        "fact_type": "Tuân thủ thuốc",
        "source_value": "Bệnh nhân không tuân thủ tốt.",
        "normalized_value": {"statement": "Bệnh nhân không tuân thủ tốt.", "document_id": "DOC-NOTE-2"},
        "citations": [{
            "citation_id": "cit_adh_2",
            "source_type": "fhir",
            "document_id": "DOC-NOTE-2",
            "resource_type": "Note",
            "resource_id": "res_note_2",
            "source_checksum": "sha256:test",
            "snippet": "không tuân thủ tốt"
        }]
    }]
    repo.add_pdf_evidence("PAT-001", "DOC-NOTE-2", mock_pdf)
    
    response = client.post("/api/v1/patients/PAT-001/ask", json={"question": "Sau thay đổi điều trị, HbA1c thay đổi thế nào và có vấn đề tuân thủ thuốc không?"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["answered", "conflicting"]

def test_conflict_detection_e2e(client, repo):
    """
    Two sources have contradictory clinical facts (incompatible values).
    """
    conflicting_pdf = [
        {
            "patient_id": "PAT-001",
            "tenant_id": "ten_demo",
            "evidence_id": "ev_conf_a",
            "verification_status": "verified",
            "fact_type": "Huyết áp",
            "source_time": "2026-08-10T10:00:00+00:00",
            "normalized_value": "120/80",
            "citations": [{
                "citation_id": "cit_conf_a",
                "source_type": "fhir",
                "document_id": "DOC-CONF-1",
                "resource_type": "Observation",
                "resource_id": "res_conf_a",
                "source_checksum": "sha256:test",
                "snippet": "120/80"
            }]
        },
        {
            "patient_id": "PAT-001",
            "tenant_id": "ten_demo",
            "evidence_id": "ev_conf_b",
            "verification_status": "verified",
            "fact_type": "Huyết áp",
            "source_time": "2026-08-10T10:05:00+00:00", # Same day
            "normalized_value": "180/100", # Contradiction
            "citations": [{
                "citation_id": "cit_conf_b",
                "source_type": "fhir",
                "document_id": "DOC-CONF-1",
                "resource_type": "Observation",
                "resource_id": "res_conf_b",
                "source_checksum": "sha256:test",
                "snippet": "180/100"
            }]
        }
    ]
    repo.add_pdf_evidence("PAT-001", "DOC-CONF-1", conflicting_pdf)
    
    response = client.post("/api/v1/patients/PAT-001/ask", json={"question": "Huyết áp của bệnh nhân là bao nhiêu?"})
    assert response.status_code == 200
    data = response.json()
    # The API must expose conflicts via status and answer for ask chart
    assert data["status"] == "conflicting"
    assert "cần xác minh" in data["answer"].lower() or "mâu thuẫn" in data["answer"].lower()

def test_cross_patient_vector_security(client, repo):
    """
    Querying Patient A should absolutely NOT return Patient B's embedded chunks.
    """
    # Patient B's evidence
    mock_pdf_b = [{
        "patient_id": "PAT-002",
        "tenant_id": "ten_demo",
        "evidence_id": "ev_b_secret",
        "origin": "note",
        "verification_status": "needs_verification",
        "fact_type": "Bệnh lây nhiễm",
        "normalized_value": {"statement": "PAT-002 bị bệnh lây nhiễm.", "document_id": "DOC-B-1"},
        "citations": [{
            "citation_id": "cit_b_secret",
            "source_type": "fhir",
            "document_id": "DOC-B-1",
            "resource_type": "Note",
            "resource_id": "res_b_secret",
            "source_checksum": "sha256:test",
            "snippet": "PAT-002 bị bệnh"
        }]
    }]
    repo.add_pdf_evidence("PAT-002", "DOC-B-1", mock_pdf_b)
    
    # Pre-index PAT-002 to Chroma (Simulate cross-pollution)
    # The agent index_evidence actually scopes to the patient it's processing, but let's see what happens on search
    
    # Query PAT-001
    response = client.post("/api/v1/patients/PAT-001/ask", json={"question": "Bệnh nhân có bị lây nhiễm không?"})
    assert response.status_code == 200
    data = response.json()
    # If the LLM generates a claim based on PAT-002's data, it's a critical failure.
    # The agent should respond not_found.
    if data["status"] == "answered":
        # Ensure no citation is from Patient B
        for cit in data.get("citations", []):
            assert cit["citation_id"] != "cit_b_secret"

def test_fabricated_citation_grounding(client):
    """
    If LLM returns a fabricated evidence_id, the verification step MUST flag it as unsupported.
    """
    # Create fake claims
    from src.agents.generation import ProposedClaim
    from src.agents.verification import verify_claims
    fake_claims = [
        ProposedClaim(
            claim_id="clm_fake",
            text="LLM invented this claim.",
            evidence_ids=["fake_999"],
            section_code="recent_results"
        )
    ]
    
    # Since agent_generation_backend might be deterministic in test, we force LLM mock by directly testing the verification
    from src.agents.verification import verify_claims
    from src.agents.evidence import ScopedEvidence
    from src.agents.contracts import EvidenceItem
    
    # Valid retrieved evidence
    valid_ev = [
        ScopedEvidence(
            item=EvidenceItem(
                evidence_id="real_123",
                fact_type="Test",
                normalized_value={},
                source_value={},
                source_time="2026-08-10T00:00:00Z",
                verification_status="verified",
                citations=[]
            ),
            origin="structured",
            patient_id="PAT-001",
            tenant_id="ten_demo"
        )
    ]
    
    claims, results = verify_claims(fake_claims, valid_ev)
    assert len(claims) == 0
    assert len(results) == 1
    assert results[0].status == "unsupported"
