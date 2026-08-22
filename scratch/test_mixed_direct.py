import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

from src.clinical.demo_repository import DemoRepository
from src.agents.adapter import AgentRequestAdapter
from src.agents.graph import build_clinical_graph

repo = DemoRepository()
patient_id = "PAT-001"
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

packet = repo.build_evidence_packet(patient_id)
memory = repo.get_patient_memory(patient_id)
q = "Sau thay đổi điều trị, HbA1c thay đổi thế nào và có vấn đề tuân thủ thuốc không?"

agent_request = AgentRequestAdapter().from_evidence_packet(
    packet,
    request_id="req_test_123",
    task_type="ask_chart",
    tenant_id="ten_demo",
    user_id="usr_doc",
    profile_versions=[],
    approved_memory=memory.model_dump(mode="json") if memory else None,
    question=q,
)

graph = build_clinical_graph()
initial_state = {
    "request": agent_request,
    "runtime_scope": {
        "tenant_id": agent_request.tenant_id,
        "patient_id": patient_id,
        "request_id": "req_test_123",
    }
}

for step in graph.stream(initial_state):
    print("--- STEP ---")
    for node_name, node_state in step.items():
        print(f"NODE: {node_name}")
        for k, v in node_state.items():
            if k == "retrieved_evidence":
                print(f"  retrieved_evidence: {[item.item.evidence_id for item in v]}")
            elif k == "proposed_claims":
                print(f"  proposed_claims: {[(c.claim_id, c.text) for c in v]}")
            elif k == "claims":
                print(f"  claims: {[(c.claim_id, c.status, c.text) for c in v]}")
            elif k == "status":
                print(f"  status: {v}")
            elif k == "public_response":
                print(f"  public_response.status: {v.status}")
                print(f"  public_response.answer: {v.answer}")
            else:
                print(f"  {k}: {v}")
