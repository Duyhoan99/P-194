"""Regenerate deterministic C2 AgentResult and verifier snapshots."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from src.agents.contracts import AgentRequest
from src.agents.graph import clinical_agent, run_agent

ROOT = Path(__file__).resolve().parents[1]
REQUEST_DIR = ROOT / "eval" / "fixtures" / "agent_requests"
SNAPSHOT_DIR = ROOT / "eval" / "snapshots"
RESULT_FIXTURES = {
    "answered": "answered_hba1c",
    "not_found": "not_found_hba1c",
    "conflicting": "conflicting_medication",
    "not_allowed": "not_allowed_treatment",
    "error": "error_cross_patient",
}


def _request(name: str) -> AgentRequest:
    return AgentRequest.model_validate_json((REQUEST_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    for status, fixture_name in RESULT_FIXTURES.items():
        result = run_agent(_request(fixture_name))
        _write(SNAPSHOT_DIR / f"agent_result_{status}.json", result.model_dump(mode="json"))

    review_request = _request("review_generation")
    review_result = run_agent(review_request)
    _write(
        SNAPSHOT_DIR / "structured_review_with_citations.json",
        review_result.model_dump(mode="json"),
    )
    state = clinical_agent.invoke(
        {
            "request": review_request,
            "runtime_scope": {
                "tenant_id": review_request.tenant_id,
                "patient_id": review_request.patient_id,
                "request_id": review_request.request_id,
            },
            "status": "running",
            "errors": [],
        },
        config={
            "configurable": {"thread_id": str(uuid.uuid4())},
            "recursion_limit": 16
        },
    )
    verification = [
        {
            "claim_id": item.claim_id,
            "status": item.status,
            "evidence_ids": list(item.evidence_ids),
            "checks": item.checks,
            "reasons": list(item.reasons),
        }
        for item in state["verification_results"]
    ]
    _write(SNAPSHOT_DIR / "verifier_per_claim.json", verification)


if __name__ == "__main__":
    main()
