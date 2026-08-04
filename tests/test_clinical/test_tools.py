import pytest
from pydantic import ValidationError

from src.agents.tools.clinical_tools import build_clinical_tools
from tests.test_clinical.conftest import allowed_context

EXPECTED_TOOL_NAMES = {
    "get_patient_overview",
    "get_encounter_timeline",
    "get_diagnoses_and_procedures",
    "get_laboratory_results",
    "get_microbiology_results",
    "get_medications",
    "get_patient_metrics",
    "check_drug_interactions",
    "get_icu_events",
}


def test_tool_factory_binds_context_and_exposes_safe_names(fake_service):
    context = allowed_context()
    tools = {tool.name: tool for tool in build_clinical_tools(fake_service, context)}

    assert set(tools) == EXPECTED_TOOL_NAMES
    result = tools["get_laboratory_results"].invoke({"subject_id": 101, "limit": 1})

    assert result["trace_id"] == context.trace_id
    assert result["records"][0]["data"] == {"itemid": 3001}
    assert fake_service._audit_sink.events[-1].trace_id == context.trace_id

    interaction = tools["check_drug_interactions"].invoke({"subject_id": 101})
    assert interaction == {"status": "NOT_LOADED", "trace_id": context.trace_id}


def test_tools_expose_only_query_fields(fake_service):
    tools = build_clinical_tools(fake_service, allowed_context())

    for tool in tools:
        assert set(tool.args_schema.model_fields) == {
            "subject_id",
            "hadm_id",
            "stay_id",
            "from_time",
            "to_time",
            "limit",
            "cursor",
        }


def test_tool_cannot_accept_model_supplied_access_context(fake_service):
    context = allowed_context()
    tools = {tool.name: tool for tool in build_clinical_tools(fake_service, context)}

    with pytest.raises(ValidationError):
        tools["get_laboratory_results"].invoke(
            {"subject_id": 101, "access_context": {"user_id": "attacker"}}
        )
