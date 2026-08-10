"""Script to generate EvidencePacket and AgentRequest fixtures for Member 2 and Member 3."""

import json
from pathlib import Path
import uuid
from src.clinical.demo_repository import DemoRepository
from src.clinical.evidence_packet import EvidencePacket, AgentRequest


def generate_fixtures():
    repo = DemoRepository()
    gold_dir = Path(__file__).parents[1] / "data" / "demo_mvp_v1" / "gold"
    gold_dir.mkdir(parents=True, exist_ok=True)

    patients = ["PAT-001", "PAT-002", "PAT-003", "PAT-004", "PAT-005", "PAT-006"]

    for pid in patients:
        events = repo.get_timeline(pid)
        wm = repo.get_watermark(pid)
        _, _, hba1c_pts = repo.get_trends(pid, "4548-4")

        timeline_data = [e.model_dump() for e in events]
        hba1c_data = [p.model_dump() for p in hba1c_pts]

        packet = EvidencePacket(
            patient_id=pid,
            data_watermark=wm,
            coverage_start="2025-01-01",
            coverage_end="2026-08-10",
            encounter_count=len(events),
            timeline=timeline_data,
            lab_trends={"4548-4": hba1c_data},
            active_conditions=[{"condition": "Đái tháo đường Típ 2", "code": "44054006"}],
            current_medications=[{"medication": "Metformin 1000mg", "status": "active"}],
            conflicts=[],
            drug_interactions=[],
            data_quality_flags=[],
        )

        agent_req = AgentRequest(
            request_id=f"req_{pid}_{uuid.uuid4().hex[:6]}",
            patient_id=pid,
            requested_profile_versions=["type_2_diabetes@1.0.0"],
            data_watermark=wm,
            language="vi",
            evidence_packet=packet,
            memory_context=[],
        )

        # Save fixtures
        ep_file = gold_dir / f"evidence_packet_{pid}.json"
        with open(ep_file, "w", encoding="utf-8") as f:
            json.dump(packet.to_dict(), f, indent=2, ensure_ascii=False)

        ar_file = gold_dir / f"agent_request_{pid}.json"
        with open(ar_file, "w", encoding="utf-8") as f:
            json.dump(agent_req.to_dict(), f, indent=2, ensure_ascii=False)

        print(f"Generated fixtures for {pid}: {ep_file.name}, {ar_file.name}")


if __name__ == "__main__":
    generate_fixtures()
