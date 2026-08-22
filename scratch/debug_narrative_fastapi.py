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

packet = repo.build_evidence_packet("PAT-001")
print("PDF EVIDENCE IN REPO:", len(repo._pdf_evidence.get("PAT-001", [])))
print("EVIDENCE IN PACKET:", [f"{item.evidence_id} ({getattr(item, 'origin', 'structured')})" for item in getattr(packet, "note_evidence", [])])

response = client.post("/api/v1/patients/PAT-001/ask", json={"question": "Bệnh nhân có báo cáo hay quên uống thuốc không?"})
print("RESPONSE STATUS CODE:", response.status_code)
print("RESPONSE JSON:", response.json())
