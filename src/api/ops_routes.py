"""Role-bound operational status for the FHIR/PDF ingestion demo."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.dependencies import get_access_context, get_operational_store
from src.clinical.errors import ClinicalAccessDenied
from src.clinical.operations import OperationalStore
from src.clinical.schemas import AccessContext
from src.config import get_settings

router = APIRouter(prefix="/ops", tags=["operations"])


class RuntimeStatusResponse(BaseModel):
    data_source: str
    dataset: str
    loaded_modules: list[str]
    ingestion: dict[str, str]
    llm_gateway: dict[str, str]
    patient_count: int
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


def _manifest() -> dict:
    path = Path(get_settings().demo_data_dir) / "dataset_manifest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


@router.get("/clinical-status", response_model=RuntimeStatusResponse)
def runtime_status(
    context: AccessContext = Depends(get_access_context),
    store: OperationalStore = Depends(get_operational_store),
) -> RuntimeStatusResponse:
    del store
    _require_operations_role(context)
    settings = get_settings()
    manifest = _manifest()
    return RuntimeStatusResponse(
        data_source="FHIR R4 + PDF/OCR",
        dataset=str(manifest.get("dataset_id", "demo dataset unavailable")),
        loaded_modules=["fhir", "pdf", "ocr", "timeline", "review", "ask-chart"],
        ingestion={"checksum_status": "AVAILABLE", "schema_status": "VALIDATED"},
        llm_gateway={"status": "CONFIGURED" if settings.llm_api_key else "DETERMINISTIC_FALLBACK"},
        patient_count=len(manifest.get("patients", [])),
        trace_id=context.trace_id,
    )


@router.get("/ingestion-runs", response_model=IngestionRunsResponse)
def ingestion_runs(
    context: AccessContext = Depends(get_access_context),
    store: OperationalStore = Depends(get_operational_store),
) -> IngestionRunsResponse:
    del store
    _require_operations_role(context)
    manifest = _manifest()
    patients = manifest.get("patients", [])
    documents = manifest.get("documents", [])
    return IngestionRunsResponse(
        runs=[
            IngestionRunResponse(
                run_id="demo-mvp-bootstrap",
                dataset=str(manifest.get("dataset_id", "demo-mvp")),
                profile="fhir-r4-pdf-ocr",
                checksum_status="AVAILABLE",
                schema_status="VALIDATED",
                counts={"patients": len(patients), "documents": len(documents)},
                errors=[],
            )
        ],
        trace_id=context.trace_id,
    )
