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


def test_smoke_event_contains_metadata_only():
    smoke = _load_smoke_module()
    output = smoke.format_safe_event("timeline", status=200, count=4, resource_id="PAT-001")
    assert output == "timeline http_status=200 count=4 resource_id=PAT-001"
    assert "HbA1c" not in output
    assert "cookie" not in output
