import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

from src.clinical.demo_repository import DemoRepository
from src.agents.adapter import AgentRequestAdapter
from src.agents.evidence import build_scoped_evidence, retrieve_evidence
from src.agents.retrieval.router import QueryPlanner

repo = DemoRepository()
patient_id = "PAT-001"

mock_pdf = [{
    "patient_id": "PAT-001", "tenant_id": "ten_demo",
    "evidence_id": "ev_forget_1", "origin": "note",
    "verification_status": "needs_verification",
    "fact_type": "Ghi chú bác sĩ",
    "source_value": "Bệnh nhân báo cáo hay quên uống thuốc buổi sáng.",
    "normalized_value": {"statement": "Bệnh nhân báo cáo hay quên uống thuốc buổi sáng.", "document_id": "DOC-NOTE-1"},
    "citations": [{
        "citation_id": "cit_forget_1", "source_type": "fhir",
        "document_id": "DOC-NOTE-1", "resource_type": "Note",
        "resource_id": "res_note_1", "source_checksum": "sha256:test",
        "snippet": "hay quên uống thuốc"
    }]
}]
repo.add_pdf_evidence("PAT-001", "DOC-NOTE-1", mock_pdf)

packet = repo.build_evidence_packet(patient_id)
memory = repo.get_patient_memory(patient_id)

q = "Bệnh nhân có báo cáo hay quên uống thuốc không?"
plan = QueryPlanner().plan(q)
print("=== PLAN ===")
print(plan.model_dump())

req = AgentRequestAdapter().from_evidence_packet(
    packet, request_id="req_1", task_type="ask_chart",
    tenant_id="ten_demo", user_id="usr_doc", profile_versions=[],
    approved_memory=memory.model_dump(mode="json") if memory else None,
    question=q,
)

scoped = build_scoped_evidence(req)
retrieved = retrieve_evidence(scoped, route=plan.model_dump(), question=q)
print(f"\n=== RETRIEVED ({len(retrieved)}) ===")
for r in retrieved:
    print(r.item.evidence_id, r.item.fact_type, r.item.source_time, r.item.normalized_value)
