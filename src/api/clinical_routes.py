"""REST endpoints backed exclusively by ``ClinicalRetrievalService``."""

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.api.dependencies import get_access_context, get_clinical_service
from src.clinical.errors import (
    ClinicalAccessDenied,
    ClinicalAuthNotConfigured,
    ClinicalDatabaseUnavailable,
    ClinicalQueryTimeout,
    ClinicalScopeInvalid,
)
from src.clinical.schemas import AccessContext, ClinicalQuery, ClinicalResponse
from src.clinical.service import ClinicalRetrievalService

router = APIRouter(prefix="/clinical", tags=["clinical"])

_ERROR_DETAILS: dict[type[Exception], str] = {
    ClinicalAuthNotConfigured: "Clinical authentication is not configured.",
    ClinicalAccessDenied: "Access to the requested clinical subject is denied.",
    ClinicalScopeInvalid: "The requested clinical scope is invalid.",
    ClinicalDatabaseUnavailable: "Clinical data is currently unavailable.",
    ClinicalQueryTimeout: "The clinical query timed out.",
}
_ERROR_STATUS_CODES: dict[type[Exception], int] = {
    ClinicalAuthNotConfigured: 503,
    ClinicalAccessDenied: 403,
    ClinicalScopeInvalid: 422,
    ClinicalDatabaseUnavailable: 503,
    ClinicalQueryTimeout: 504,
}


def _trace_id(request: Request) -> str:
    """Return the request correlation ID, creating one before an early error."""
    trace_id = getattr(request.state, "clinical_trace_id", None)
    if trace_id is None:
        trace_id = str(uuid4())
        request.state.clinical_trace_id = trace_id
    return trace_id


def clinical_error_response(
    request: Request, error: Exception, *, trace_id: str | None = None
) -> JSONResponse:
    """Serialize a clinical domain error without exposing database details."""
    error_type = type(error)
    return JSONResponse(
        status_code=_ERROR_STATUS_CODES.get(error_type, 503),
        content={
            "detail": _ERROR_DETAILS.get(error_type, "Clinical data is currently unavailable."),
            "trace_id": trace_id or _trace_id(request),
        },
    )


def register_clinical_error_handlers(app: Any) -> None:
    """Register consistent, traceable domain-error responses on the FastAPI app."""

    for error_type in _ERROR_STATUS_CODES:

        async def handler(request: Request, error: Exception) -> JSONResponse:
            return clinical_error_response(request, error)

        app.add_exception_handler(error_type, handler)

    async def validation_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        default_response = await request_validation_exception_handler(request, error)
        if not request.url.path.startswith("/api/v1/clinical/"):
            return default_response

        content = json.loads(default_response.body)
        content["trace_id"] = str(uuid4())
        return JSONResponse(
            status_code=422,
            content=content,
            headers=dict(default_response.headers),
        )

    app.add_exception_handler(RequestValidationError, validation_handler)


def _retrieve(
    request: Request,
    service_method: Callable[[AccessContext, ClinicalQuery], ClinicalResponse],
    context: AccessContext,
    subject_id: int,
    hadm_id: int | None,
    stay_id: int | None,
    from_time: datetime | None,
    to_time: datetime | None,
    limit: int,
) -> ClinicalResponse | JSONResponse:
    request.state.clinical_trace_id = context.trace_id
    try:
        query = ClinicalQuery(
            subject_id=subject_id,
            hadm_id=hadm_id,
            stay_id=stay_id,
            from_time=from_time,
            to_time=to_time,
            limit=limit,
        )
    except ValidationError:
        return clinical_error_response(request, ClinicalScopeInvalid(), trace_id=context.trace_id)

    try:
        response = service_method(context, query)
    except (
        ClinicalAccessDenied,
        ClinicalScopeInvalid,
        ClinicalDatabaseUnavailable,
        ClinicalQueryTimeout,
    ) as error:
        return clinical_error_response(request, error, trace_id=context.trace_id)

    if response.status == "DENIED":
        return clinical_error_response(request, ClinicalAccessDenied(), trace_id=response.trace_id)
    return response


@router.get("/patients/{subject_id}", response_model=ClinicalResponse)
def get_patient_overview(
    request: Request,
    subject_id: int,
    hadm_id: int | None = None,
    stay_id: int | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    limit: int = 200,
    context: AccessContext = Depends(get_access_context),
    service: ClinicalRetrievalService = Depends(get_clinical_service),
) -> ClinicalResponse | JSONResponse:
    return _retrieve(
        request, service.get_patient_overview, context, subject_id, hadm_id, stay_id, from_time, to_time, limit
    )


@router.get("/patients/{subject_id}/timeline", response_model=ClinicalResponse)
def get_encounter_timeline(
    request: Request,
    subject_id: int,
    hadm_id: int | None = None,
    stay_id: int | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    limit: int = 200,
    context: AccessContext = Depends(get_access_context),
    service: ClinicalRetrievalService = Depends(get_clinical_service),
) -> ClinicalResponse | JSONResponse:
    return _retrieve(
        request, service.get_encounter_timeline, context, subject_id, hadm_id, stay_id, from_time, to_time, limit
    )


@router.get("/patients/{subject_id}/diagnoses-procedures", response_model=ClinicalResponse)
def get_diagnoses_and_procedures(
    request: Request,
    subject_id: int,
    hadm_id: int | None = None,
    stay_id: int | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    limit: int = 200,
    context: AccessContext = Depends(get_access_context),
    service: ClinicalRetrievalService = Depends(get_clinical_service),
) -> ClinicalResponse | JSONResponse:
    return _retrieve(
        request,
        service.get_diagnoses_and_procedures,
        context,
        subject_id,
        hadm_id,
        stay_id,
        from_time,
        to_time,
        limit,
    )


@router.get("/patients/{subject_id}/labs", response_model=ClinicalResponse)
def get_laboratory_results(
    request: Request,
    subject_id: int,
    hadm_id: int | None = None,
    stay_id: int | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    limit: int = 200,
    context: AccessContext = Depends(get_access_context),
    service: ClinicalRetrievalService = Depends(get_clinical_service),
) -> ClinicalResponse | JSONResponse:
    return _retrieve(
        request, service.get_laboratory_results, context, subject_id, hadm_id, stay_id, from_time, to_time, limit
    )


@router.get("/patients/{subject_id}/microbiology", response_model=ClinicalResponse)
def get_microbiology_results(
    request: Request,
    subject_id: int,
    hadm_id: int | None = None,
    stay_id: int | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    limit: int = 200,
    context: AccessContext = Depends(get_access_context),
    service: ClinicalRetrievalService = Depends(get_clinical_service),
) -> ClinicalResponse | JSONResponse:
    return _retrieve(
        request, service.get_microbiology_results, context, subject_id, hadm_id, stay_id, from_time, to_time, limit
    )


@router.get("/patients/{subject_id}/icu-events", response_model=ClinicalResponse)
def get_icu_events(
    request: Request,
    subject_id: int,
    hadm_id: int | None = None,
    stay_id: int | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    limit: int = 200,
    context: AccessContext = Depends(get_access_context),
    service: ClinicalRetrievalService = Depends(get_clinical_service),
) -> ClinicalResponse | JSONResponse:
    return _retrieve(
        request, service.get_icu_events, context, subject_id, hadm_id, stay_id, from_time, to_time, limit
    )
