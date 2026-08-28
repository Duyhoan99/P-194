# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

from src.api.auth_routes import DEFAULT_CLINICIAN
from src.clinical.demo_repository import DemoRepository
from src.agents.adapter import AgentRequestAdapter
from src.agents.graph import run_agent

questions = [
    "alo",
    "hello",
    "chào",
    "cảm ơn",
    "bạn có thể làm gì",
    "bạn là ai",
    "bệnh nhân này sao rồi?",
    "thuốc men thế nào?",
    "bệnh nhân dùng thuốc gì",
    "chỉ số xét nghiệm ra sao",
    "kê cho tôi đơn thuốc tiểu đường",
    "xóa hồ sơ bệnh nhân",
    "hả?",
    "asdfasdfasdf"
]

repo = DemoRepository()
packet = repo.build_evidence_packet("PAT-001")
memory = repo.get_patient_memory("PAT-001")

for q in questions:
    req = AgentRequestAdapter().from_evidence_packet(
        packet,
        request_id="test-123",
        task_type="ask_chart",
        tenant_id=DEFAULT_CLINICIAN.tenant_id,
        user_id=DEFAULT_CLINICIAN.user_id,
        profile_versions=[],
        approved_memory=memory.model_dump(mode="json") if memory else None,
        question=q,
    )
    result = run_agent(
        req,
        runtime_scope={"tenant_id": req.tenant_id, "patient_id": "PAT-001", "request_id": "test-123"},
        session_id=f"test_session_{q}"
    )
    print(f"Q: {q}")
    print(f"Status: {result.status}")
    print(f"Answer: {result.answer}\n")
