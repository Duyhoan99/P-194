import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

from src.clinical.demo_repository import DemoRepository
from src.agents.adapter import AgentRequestAdapter
from src.agents.nodes.clinical_nodes import (
    validate_scope_node, classify_question_node,
    retrieve_evidence_node, generate_grounded_node,
    verify_claims_node, abstain_node, finalize_response_node
)

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

req = AgentRequestAdapter().from_evidence_packet(
    packet, request_id="req_1", task_type="ask_chart",
    tenant_id="ten_demo", user_id="usr_doc", profile_versions=[],
    approved_memory=memory.model_dump(mode="json") if memory else None,
    question=q,
)

state = {
    "request": req,
    "runtime_scope": {
        "tenant_id": req.tenant_id,
        "patient_id": patient_id,
        "request_id": "req_1",
    }
}
s1 = validate_scope_node(state)
state.update(s1)
print("1. VALIDATE SCOPE:", s1)

s2 = classify_question_node(state)
state.update(s2)
print("2. CLASSIFY:", s2)

s3 = retrieve_evidence_node(state)
state.update(s3)
print(f"3. RETRIEVE ({len(s3.get('retrieved_evidence', []))} items):", [e.item.evidence_id for e in s3.get("retrieved_evidence", [])])

s4 = generate_grounded_node(state)
state.update(s4)
print(f"4. GENERATE ({len(s4.get('proposed_claims', []))} claims):", [(c.claim_id, c.text) for c in s4.get("proposed_claims", [])])

s5 = verify_claims_node(state)
state.update(s5)
print("5. VERIFY:", s5.get("status"), [(c.claim_id, c.status) for c in s5.get("claims", [])])

s6 = finalize_response_node(state)
print("6. FINALIZE STATUS:", s6.get("result").status)
print("6. FINALIZE ANSWER:", s6.get("result").answer)
