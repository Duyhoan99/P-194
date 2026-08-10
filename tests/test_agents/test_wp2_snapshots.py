import json
from pathlib import Path

from src.agents.graph import run_agent

from .test_wp2_contract import load_request

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = ROOT / "eval" / "snapshots"

CASES = {
    "answered": "answered_hba1c",
    "not_found": "not_found_hba1c",
    "conflicting": "conflicting_medication",
    "not_allowed": "not_allowed_treatment",
    "error": "error_cross_patient",
}


def test_agent_result_snapshots() -> None:
    for status, fixture_name in CASES.items():
        expected = json.loads((SNAPSHOTS / f"agent_result_{status}.json").read_text(encoding="utf-8"))
        actual = run_agent(load_request(fixture_name)).model_dump(mode="json")
        assert actual == expected


def test_structured_review_snapshot() -> None:
    expected = json.loads((SNAPSHOTS / "structured_review_with_citations.json").read_text(encoding="utf-8"))
    actual = run_agent(load_request("review_generation")).model_dump(mode="json")
    assert actual == expected
