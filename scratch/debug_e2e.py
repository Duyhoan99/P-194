import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

from src.clinical.demo_repository import DemoRepository
from src.agents.adapter import AgentRequestAdapter
from src.agents.evidence import build_scoped_evidence, retrieve_evidence
from src.agents.generation import compose_atomic_claims, compose_atomic_claims_llm
from src.agents.verification import verify_claims
from src.agents.retrieval.router import QueryPlanner
from src.agents.llm_client import get_llm_runtime

repo = DemoRepository()
patient_id = "PAT-001"
packet = repo.build_evidence_packet(patient_id)
memory = repo.get_patient_memory(patient_id)

q = "3 HbA1c gần nhất của bệnh nhân là gì?"
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

runtime = get_llm_runtime()
print(f"\n=== RUNTIME AVAILABLE: {runtime.available} ===")

if runtime.available:
    res = compose_atomic_claims_llm(retrieved, runtime.client, question=q)
    print("LLM RES:", res)
    proposed = res.get("claims", [])
else:
    proposed = compose_atomic_claims(retrieved)

print(f"\n=== PROPOSED ({len(proposed)}) ===")
for p in proposed:
    print(p.claim_id, p.text, p.evidence_ids)

claims, ver = verify_claims(proposed, retrieved)
print(f"\n=== VERIFIED ({len(claims)}) ===")
for c in claims:
    print(c.claim_id, c.status, c.text)

print(f"\n=== VERIFICATION CHECKS ===")
for v in ver:
    print(v.claim_id, v.status, v.checks, v.reasons)
