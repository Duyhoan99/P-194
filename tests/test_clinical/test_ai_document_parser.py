import pytest

from src.clinical.ai_document_parser import _deterministic_regex_parse


@pytest.mark.parametrize("unit", ["mL/min", "ml/min", "ML/MIN"])
def test_egfr_unit_matching_is_case_insensitive(unit: str) -> None:
    parsed = _deterministic_regex_parse(f"eGFR: 72 {unit}/1.73m2")

    assert len(parsed.observations) == 1
    observation = parsed.observations[0]
    assert observation.code == "33914-3"
    assert observation.value == 72
    assert observation.unit == "mL/min/1.73m2"
