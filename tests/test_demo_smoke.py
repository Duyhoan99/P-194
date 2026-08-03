import importlib.util
from pathlib import Path


def _load_smoke_module():
    script_path = Path(__file__).parents[1] / "scripts" / "run_demo_smoke.py"
    spec = importlib.util.spec_from_file_location("run_demo_smoke", script_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Smoke script could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_event_format_discards_clinical_values_rows_and_secrets():
    smoke = _load_smoke_module()

    output = smoke.format_safe_event(
        "laboratory evidence",
        {
            "status": "SUCCESS",
            "trace_id": "trace-123",
            "records": [
                {
                    "data": {"label": "Creatinine", "valuenum": 1.2},
                    "lineage": {"table": "labevents"},
                }
            ],
            "summary": "Clinical summary text must not be printed",
            "api_key": "never-print-this",
        },
    )

    assert output == "laboratory evidence status=SUCCESS record_count=1 trace_id=trace-123 source_tables=labevents"
    assert "Creatinine" not in output
    assert "1.2" not in output
    assert "summary" not in output
    assert "never-print-this" not in output
