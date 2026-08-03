"""Safe, role-bound operational status endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.dependencies import get_access_context, get_operational_store
from src.clinical.errors import ClinicalAccessDenied
from src.clinical.operations import OperationalStore
from src.clinical.schemas import AccessContext
from src.config import get_settings

router = APIRouter(prefix="/ops", tags=["operations"])


class ClinicalStatusResponse(BaseModel):
    backend: str
    database: dict[str, str]
    loaded_modules: list[str]
    source_profile: str
    ingestion: dict[str, str]
    llm_gateway: dict[str, str]
    clinical_tools: dict[str, object]
    latency: dict[str, int]
    trace_id: str


class IngestionRunResponse(BaseModel):
    run_id: str
    dataset: str
    profile: str
    checksum_status: str
    schema_status: str
    counts: dict[str, int]
    errors: list[str]


class IngestionRunsResponse(BaseModel):
    runs: list[IngestionRunResponse]
    trace_id: str


def _require_operations_role(context: AccessContext) -> None:
    if context.role not in {"ADMIN", "DATA_STEWARD"}:
        raise ClinicalAccessDenied


@router.get("/clinical-status", response_model=ClinicalStatusResponse)
def clinical_status(
    context: AccessContext = Depends(get_access_context),
    store: OperationalStore = Depends(get_operational_store),
) -> ClinicalStatusResponse:
    del store
    _require_operations_role(context)
    settings = get_settings()
    return ClinicalStatusResponse(
        backend=settings.clinical_backend,
        database={"status": "CONFIGURED"},
        loaded_modules=["overview", "timeline", "diagnoses-procedures", "laboratory", "microbiology", "icu-events"],
        source_profile=settings.clinical_source_profile,
        ingestion={"checksum_status": "NOT_RECORDED", "schema_status": "NOT_VALIDATED"},
        llm_gateway={"status": "CONFIGURED" if settings.openai_api_key else "UNAVAILABLE"},
        clinical_tools={"status": "AVAILABLE", "count": 6},
        latency={"query_timeout_ms": int(settings.clinical_query_timeout_seconds * 1000)},
        trace_id=context.trace_id,
    )


@router.get("/ingestion-runs", response_model=IngestionRunsResponse)
def ingestion_runs(
    context: AccessContext = Depends(get_access_context),
    store: OperationalStore = Depends(get_operational_store),
) -> IngestionRunsResponse:
    del store
    _require_operations_role(context)
    settings = get_settings()
    return IngestionRunsResponse(
        runs=[
            IngestionRunResponse(
                run_id="synthetic-demo-bootstrap",
                dataset=settings.clinical_source_dataset,
                profile=settings.clinical_source_profile,
                checksum_status="NOT_RECORDED",
                schema_status="NOT_VALIDATED",
                counts={"sources": 0, "errors": 0},
                errors=[],
            )
        ],
        trace_id=context.trace_id,
    )
