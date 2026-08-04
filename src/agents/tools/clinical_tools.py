"""LangChain adapters for access-controlled clinical retrievals."""

from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import ConfigDict

from src.clinical.schemas import AccessContext, ClinicalQuery
from src.clinical.service import ClinicalRetrievalService


class ClinicalToolInput(ClinicalQuery):
    """Model-visible query fields for every clinical retrieval tool."""

    model_config = ConfigDict(extra="forbid")


_TOOL_METHODS = (
    "get_patient_overview",
    "get_encounter_timeline",
    "get_diagnoses_and_procedures",
    "get_laboratory_results",
    "get_microbiology_results",
    "get_medications",
    "get_patient_metrics",
    "get_icu_events",
)


def build_clinical_tools(
    service: ClinicalRetrievalService, access_context: AccessContext
) -> list[BaseTool]:
    """Build clinical retrieval tools with the authenticated context bound in closures."""
    tools = [_build_tool(service, access_context, method_name) for method_name in _TOOL_METHODS]
    tools.append(_build_interaction_tool(access_context))
    return tools


def _build_interaction_tool(access_context: AccessContext) -> StructuredTool:
    def check_drug_interactions(**_: Any) -> dict[str, str]:
        return {"status": "NOT_LOADED", "trace_id": access_context.trace_id}

    return StructuredTool.from_function(
        func=check_drug_interactions,
        name="check_drug_interactions",
        description="Drug interaction knowledge base is not loaded; never infer an interaction.",
        args_schema=ClinicalToolInput,
    )


def _build_tool(
    service: ClinicalRetrievalService, access_context: AccessContext, method_name: str
) -> StructuredTool:
    def retrieve(
        subject_id: int,
        hadm_id: int | None = None,
        stay_id: int | None = None,
        from_time: Any = None,
        to_time: Any = None,
        limit: int = 200,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        query = ClinicalToolInput(
            subject_id=subject_id,
            hadm_id=hadm_id,
            stay_id=stay_id,
            from_time=from_time,
            to_time=to_time,
            limit=limit,
            cursor=cursor,
        )
        response = getattr(service, method_name)(access_context, query)
        return response.model_dump(mode="json")

    retrieve.__name__ = method_name
    retrieve.__doc__ = f"Retrieve clinical data using the {method_name} access-controlled service method."
    return StructuredTool.from_function(
        func=retrieve,
        name=method_name,
        description=retrieve.__doc__,
        args_schema=ClinicalToolInput,
    )
