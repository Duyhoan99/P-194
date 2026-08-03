"""Thin FastAPI adapters for clinical summary generation and retrieval."""

from uuid import UUID

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ValidationError

from src.api.clinical_routes import clinical_error_response
from src.api.dependencies import (
    get_access_context,
    get_review_service,
    get_summary_repository,
    get_summary_service,
)
from src.clinical.errors import (
    ClinicalAccessDenied,
    ClinicalScopeInvalid,
    ClinicalSummaryNotFound,
    ReviewPolicyError,
)
from src.clinical.review import ReviewService
from src.clinical.schemas import AccessContext, ClinicalQuery
from src.clinical.summary_repository import SQLiteSummaryRepository, SummaryVersion
from src.clinical.summary_schemas import ClinicalSummaryDraft
from src.clinical.summary_service import ClinicalSummaryService

router = APIRouter(prefix="/clinical", tags=["clinical-summaries"])


class GenerateSummaryRequest(BaseModel):
    hadm_id: int | None = None
    stay_id: int | None = None


class EditSummaryRequest(BaseModel):
    draft: ClinicalSummaryDraft
    reason: str | None = None


class AssignedPatientsResponse(BaseModel):
    patients: list[int]
    trace_id: str


def _review_error(request: Request, status_code: int) -> JSONResponse:
    response = clinical_error_response(request, ReviewPolicyError())
    response.status_code = status_code
    return response


@router.get("/patients", response_model=AssignedPatientsResponse)
def get_assigned_patients(context: AccessContext = Depends(get_access_context)) -> AssignedPatientsResponse:
    """Return only server-authorized patient identifiers from the signed context."""
    if context.role != "DOCTOR":
        raise ClinicalAccessDenied
    return AssignedPatientsResponse(patients=sorted(context.assigned_subject_ids), trace_id=context.trace_id)


@router.post("/patients/{subject_id}/summaries", response_model=SummaryVersion, status_code=201)
def generate_summary(
    subject_id: int,
    payload: GenerateSummaryRequest | None = Body(default=None),
    context: AccessContext = Depends(get_access_context),
    service: ClinicalSummaryService = Depends(get_summary_service),
    repository: SQLiteSummaryRepository = Depends(get_summary_repository),
) -> SummaryVersion:
    try:
        query = ClinicalQuery(
            subject_id=subject_id,
            hadm_id=payload.hadm_id if payload else None,
            stay_id=payload.stay_id if payload else None,
        )
    except ValidationError as error:
        raise ClinicalScopeInvalid from error
    draft = service.generate(context, query)
    return repository.create_draft(draft, context.user_id)


@router.get("/summaries/{summary_id}", response_model=SummaryVersion)
def get_summary(
    summary_id: UUID,
    request: Request,
    context: AccessContext = Depends(get_access_context),
    service: ReviewService = Depends(get_review_service),
) -> SummaryVersion | JSONResponse:
    try:
        return service.get(summary_id, context)
    except ClinicalSummaryNotFound:
        return _review_error(request, 404)


@router.patch("/summaries/{summary_id}", response_model=SummaryVersion)
def edit_summary(
    summary_id: UUID,
    payload: EditSummaryRequest,
    request: Request,
    context: AccessContext = Depends(get_access_context),
    service: ReviewService = Depends(get_review_service),
) -> SummaryVersion | JSONResponse:
    try:
        return service.edit(summary_id, context, payload.draft, payload.reason)
    except ClinicalSummaryNotFound:
        return _review_error(request, 404)
    except ReviewPolicyError:
        return _review_error(request, 422)


@router.get("/summaries/{summary_id}/versions", response_model=list[SummaryVersion])
def list_summary_versions(
    summary_id: UUID,
    request: Request,
    context: AccessContext = Depends(get_access_context),
    service: ReviewService = Depends(get_review_service),
) -> list[SummaryVersion] | JSONResponse:
    try:
        return service.list_versions(summary_id, context)
    except ClinicalSummaryNotFound:
        return _review_error(request, 404)


@router.post("/summaries/{summary_id}/export", response_class=Response, response_model=None)
def export_summary(
    summary_id: UUID,
    request: Request,
    context: AccessContext = Depends(get_access_context),
    service: ReviewService = Depends(get_review_service),
) -> Response | JSONResponse:
    try:
        version = service.export(summary_id, context)
    except ClinicalSummaryNotFound:
        return _review_error(request, 404)
    except ReviewPolicyError:
        return _review_error(request, 409)
    return Response(
        content=_summary_pdf(version),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="clinical-summary-{version.summary_id}.pdf"',
            "X-Trace-Id": context.trace_id,
        },
    )


def _summary_pdf(version: SummaryVersion) -> bytes:
    """Render only the persisted summary contract into a minimal portable PDF."""
    draft = version.draft
    lines = [
        "Clinical Summary",
        f"De-identified subject ID: {draft.subject_id}",
        f"Status: {version.status}",
        f"Version: {version.version_number}",
        f"Reviewer: {version.actor_id}",
        "",
    ]
    for section, claims in draft.sections.items():
        lines.append(section)
        lines.extend(f"- {claim.text} [citations: {', '.join(claim.citation_ids)}]" for claim in claims)
    lines.extend(["", "Citation references:"])
    lines.extend(f"- {citation.citation_id}" for citation in draft.citations)
    lines.extend(["", "Conflicts:"])
    lines.extend(f"- {conflict.topic}: {conflict.status}" for conflict in draft.conflicts)
    lines.extend(["", "Limitations:"])
    lines.extend(f"- {limitation}" for limitation in draft.limitations)
    if version.status not in {"APPROVED", "EXPORTED"}:
        lines.append("DRAFT - NOT FOR CLINICAL USE")
    return _minimal_pdf(lines)


def _minimal_pdf(lines: list[str]) -> bytes:
    escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    commands = ["BT", "/F1 10 Tf", "72 760 Td", "14 TL"]
    commands.extend(f"({line.encode('ascii', 'replace').decode('ascii')}) Tj T*" for line in escaped)
    commands.append("ET")
    content = "\n".join(commands).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    pdf.extend(b"".join(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:]))
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(pdf)
