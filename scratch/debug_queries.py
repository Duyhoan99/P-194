import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
os.environ["AGENT_GENERATION_BACKEND"] = "deterministic"
os.environ["LLM_API_KEY"] = ""

from src.clinical.demo_repository import DemoRepository
from src.agents.adapter import AgentRequestAdapter
from src.agents.graph import run_agent
from src.agents.retrieval.router import QueryPlanner

repo = DemoRepository()
patient_id = "PAT-001"
packet = repo.build_evidence_packet(patient_id)
memory = repo.get_patient_memory(patient_id)

queries = [
    "Diễn tiến HbA1c xuyên suốt các lần đo được ghi nhận ra sao?",
    "Cho biết diễn tiến của hemoglobin A1c trong hồ sơ.",
    "Cho biết những tình trạng bệnh đang được theo dõi.",
    "Xin điểm lại các thông tin y khoa chính trong hồ sơ này.",
]

for q in queries:
    req = AgentRequestAdapter().from_evidence_packet(
        packet, request_id="req_debug", task_type="ask_chart",
        tenant_id="ten_demo", user_id="usr_doc", profile_versions=[],
        approved_memory=memory.model_dump(mode="json") if memory else None,
        question=q,
    )
    result = run_agent(req)
    print(f"=== QUERY: {q} ===")
    print(f"STATUS: {result.status}")
    print(f"ANSWER: {result.answer[:120] if result.answer else 'NONE'}")
    print(f"CITATIONS: {len(result.citations)}")
    print()
