import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "data" / "demo_mvp_v1" / "gold"


def _gold_cases() -> list[tuple[str, dict]]:
    cases: list[tuple[str, dict]] = []
    for path in sorted(GOLD.iterdir()):
        if path.suffix == ".jsonl":
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        else:
            rows = json.loads(path.read_text(encoding="utf-8"))["cases"]
        cases.extend((path.name, row) for row in rows)
    return cases


def test_demo_manifest_version_and_all_49_gold_cases_are_loaded() -> None:
    manifest = json.loads((ROOT / "data" / "demo_mvp_v1" / "dataset_manifest.json").read_text(encoding="utf-8"))
    cases = _gold_cases()
    assert manifest["version"] == "1.3.0"
    assert len(cases) == 49
    assert len({case["case_id"] for _, case in cases}) == 49


def test_gold_patient_and_document_ids_come_from_manifest() -> None:
    manifest = json.loads((ROOT / "data" / "demo_mvp_v1" / "dataset_manifest.json").read_text(encoding="utf-8"))
    patient_ids = {patient["patient_id"] for patient in manifest["patients"]}
    document_ids = {document["document_id"] for document in manifest["documents"]}
    for _, case in _gold_cases():
        if case.get("patient_id"):
            assert case["patient_id"] in patient_ids
        if case.get("document_id"):
            assert case["document_id"] in document_ids
