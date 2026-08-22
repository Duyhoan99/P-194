import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

from fastapi.testclient import TestClient
from src.main import app
from src.clinical.demo_repository import DemoRepository
from src.api.dependencies import get_demo_repository

repo = DemoRepository()
app.dependency_overrides[get_demo_repository] = lambda: repo
client = TestClient(app)

# 1. Mixed retrieval
mock_pdf = [{
    "patient_id": "PAT-001", "tenant_id": "ten_demo",
    "evidence_id": "ev_adherence_2", "origin": "note",
    "verification_status": "needs_verification",
    "fact_type": "Tuân thủ thuốc",
    "source_value": "Bệnh nhân không tuân thủ tốt.",
    "normalized_value": {"statement": "Bệnh nhân không tuân thủ tốt.", "document_id": "DOC-NOTE-2"},
    "citations": [{
        "citation_id": "cit_adh_2", "source_type": "fhir",
        "document_id": "DOC-NOTE-2", "resource_type": "Note",
        "resource_id": "res_note_2", "source_checksum": "sha256:test",
        "snippet": "không tuân thủ tốt"
    }]
}]
repo.add_pdf_evidence("PAT-001", "DOC-NOTE-2", mock_pdf)
res_mixed = client.post("/api/v1/patients/PAT-001/ask", json={"question": "Sau thay đổi điều trị, HbA1c thay đổi thế nào và có vấn đề tuân thủ thuốc không?"})
print("MIXED STATUS:", res_mixed.status_code, res_mixed.json())

# 2. Conflict detection
repo2 = DemoRepository()
app.dependency_overrides[get_demo_repository] = lambda: repo2
client2 = TestClient(app)
conflicting_pdf = [
    {
        "patient_id": "PAT-001", "tenant_id": "ten_demo",
        "evidence_id": "ev_conf_a", "verification_status": "verified",
        "fact_type": "Huyết áp", "source_time": "2026-08-10T10:00:00+00:00",
        "normalized_value": "120/80",
        "citations": [{"citation_id": "cit_conf_a", "source_type": "fhir", "document_id": "DOC-CONF-1", "resource_type": "Observation", "resource_id": "res_conf_a", "source_checksum": "sha256:test", "snippet": "120/80"}]
    },
    {
        "patient_id": "PAT-001", "tenant_id": "ten_demo",
        "evidence_id": "ev_conf_b", "verification_status": "verified",
        "fact_type": "Huyết áp", "source_time": "2026-08-10T10:05:00+00:00",
        "normalized_value": "180/100",
        "citations": [{"citation_id": "cit_conf_b", "source_type": "fhir", "document_id": "DOC-CONF-1", "resource_type": "Observation", "resource_id": "res_conf_b", "source_checksum": "sha256:test", "snippet": "180/100"}]
    }
]
repo2.add_pdf_evidence("PAT-001", "DOC-CONF-1", conflicting_pdf)
res_conf = client2.post("/api/v1/patients/PAT-001/ask", json={"question": "Huyết áp của bệnh nhân là bao nhiêu?"})
print("CONF STATUS:", res_conf.status_code, res_conf.json())
