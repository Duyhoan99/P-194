"""Thin FastAPI adapters for clinician review actions."""

from uuid import UUID

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Request
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

from src.api.clinical_routes import clinical_error_response
from src.api.dependencies import get_access_context, get_review_service
from src.clinical.errors import ClinicalSummaryNotFound, ReviewPolicyError
from src.clinical.review import ReviewChecklist, ReviewService
from src.clinical.schemas import AccessContext
from src.clinical.summary_repository import SummaryVersion

router = APIRouter(prefix="/clinical/summaries", tags=["clinical-summary-review"])


class RejectSummaryRequest(BaseModel):
    reason: str = Field(min_length=1)


def _review_error(request: Request, status_code: int) -> JSONResponse:
    response = clinical_error_response(request, ReviewPolicyError())
    response.status_code = status_code
    return response


@router.post("/{summary_id}/reject", response_model=SummaryVersion)
def reject_summary(
    summary_id: UUID,
    payload: RejectSummaryRequest,
    request: Request,
    context: AccessContext = Depends(get_access_context),
    service: ReviewService = Depends(get_review_service),
) -> SummaryVersion | JSONResponse:
    try:
        return service.reject(summary_id, context, payload.reason)
    except ClinicalSummaryNotFound:
        return _review_error(request, 404)
    except ReviewPolicyError:
        return _review_error(request, 422)


@router.post("/{summary_id}/approve", response_model=SummaryVersion)
def approve_summary(
    summary_id: UUID,
    checklist: ReviewChecklist,
    request: Request,
    context: AccessContext = Depends(get_access_context),
    service: ReviewService = Depends(get_review_service),
) -> SummaryVersion | JSONResponse:
    try:
        return service.approve(summary_id, context, checklist)
    except ClinicalSummaryNotFound:
        return _review_error(request, 404)
    except ReviewPolicyError:
        return _review_error(request, 422)
