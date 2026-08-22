import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

from src.clinical.demo_repository import DemoRepository
from src.agents.adapter import AgentRequestAdapter
from src.agents.nodes.clinical_nodes import (
    validate_scope_node, classify_question_node,
    retrieve_evidence_node, generate_grounded_node,
    verify_claims_node, finalize_response_node
)

repo = DemoRepository()
patient_id = "PAT-001"

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

packet = repo.build_evidence_packet(patient_id)
memory = repo.get_patient_memory(patient_id)
q = "Huyết áp của bệnh nhân là bao nhiêu?"

req = AgentRequestAdapter().from_evidence_packet(
    packet, request_id="req_conf_1", task_type="ask_chart",
    tenant_id="ten_demo", user_id="usr_doc", profile_versions=[],
    approved_memory=memory.model_dump(mode="json") if memory else None,
    question=q,
)

state = {
    "request": req,
    "runtime_scope": {
        "tenant_id": req.tenant_id,
        "patient_id": patient_id,
        "request_id": "req_conf_1",
    }
}
state.update(validate_scope_node(state))
state.update(classify_question_node(state))
state.update(retrieve_evidence_node(state))
print("CONFLICTS AFTER RETRIEVE:", state.get("conflicts"))
print("RETRIEVED ITEMS:", [e.item.evidence_id for e in state.get("retrieved_evidence", [])])
state.update(generate_grounded_node(state))
print("CONFLICTS AFTER GENERATE:", state.get("conflicts"))
state.update(verify_claims_node(state))
print("STATUS AFTER VERIFY:", state.get("status"))
s_fin = finalize_response_node(state)
print("FINAL RESPONSE STATUS:", s_fin.get("public_response").status)
print("FINAL RESPONSE ANSWER:", s_fin.get("public_response").answer)
