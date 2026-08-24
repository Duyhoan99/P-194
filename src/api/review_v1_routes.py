"""Clinical Review REST endpoints adhering strictly to API_CONTRACT.md sections 4.7, 4.10, 4.12."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from loguru import logger
from pydantic import BaseModel, Field

from src.agents.adapter import AgentRequestAdapter
from src.agents.graph import run_agent
from src.api.auth_routes import DEFAULT_CLINICIAN
from src.api.dependencies import get_demo_repository
from src.clinical.canonical import ReviewResponse
from src.clinical.demo_repository import DemoRepository
from src.clinical.errors import ReviewPolicyError

router = APIRouter(tags=["reviews"])


class GenerateReviewRequest(BaseModel):
    profile_versions: list[str] = Field(default_factory=lambda: ["type_2_diabetes@1.0.0"])
    language: str = "vi"


class PatchReviewRequest(BaseModel):
    expected_version: int
    sections: list[dict]
    edit_reason: str | None = None


class ApproveReviewRequest(BaseModel):
    review_version_id: str
    expected_version: int
    clinician_confirmation: bool


class RejectReviewRequest(BaseModel):
    review_version_id: str | None = None
    expected_version: int
    reason: str


class VersionListResponse(BaseModel):
    items: list[dict]
    page: int
    page_size: int
    total: int


@router.post("/patients/{patient_id}/reviews/generate", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def generate_review(
    patient_id: str,
    request: Request,
    response: Response,
    payload: GenerateReviewRequest | None = None,
    repo: DemoRepository = Depends(get_demo_repository),
) -> ReviewResponse:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    profiles = payload.profile_versions if payload else ["type_2_diabetes@1.0.0"]
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
    packet = repo.build_evidence_packet(patient_id)
    memory = repo.get_patient_memory(patient_id)
    agent_request = AgentRequestAdapter().from_evidence_packet(
        packet,
        request_id=request_id,
        task_type="review_generation",
        tenant_id=DEFAULT_CLINICIAN.tenant_id,
        user_id=DEFAULT_CLINICIAN.user_id,
        profile_versions=profiles,
        approved_memory=memory.model_dump(mode="json") if memory else None,
    )
    agent_result = run_agent(
        agent_request,
        runtime_scope={
            "tenant_id": agent_request.tenant_id,
            "patient_id": patient_id,
            "request_id": request_id,
        },
    )
    if agent_result.status not in {"answered", "conflicting"}:
        raise HTTPException(
            status_code=503,
            detail={"code": "AGENT_UNAVAILABLE", "message": "Không thể tạo bản rà soát an toàn từ dữ liệu hiện tại."},
        )

    try:
        review = repo.generate_review(patient_id, profiles, agent_result, packet)
    except ValueError:
        raise HTTPException(
            status_code=503,
            detail={"code": "AGENT_RESULT_INVALID", "message": "Kết quả AI không khớp phạm vi dữ liệu đã khóa."},
        ) from None
    response.headers["X-Request-ID"] = request_id
    return review


@router.get("/patients/{patient_id}/review", response_model=ReviewResponse)
def get_review(
    patient_id: str,
    version: int | None = Query(default=None),
    review_version_id: str | None = Query(default=None),
    allow_missing: bool = Query(
        default=False,
        description="Return 204 when no review exists; intended for optional UI lookups.",
    ),
    repo: DemoRepository = Depends(get_demo_repository),
) -> ReviewResponse | Response:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    rev = repo.get_review(patient_id, version, review_version_id)
    if not rev:
        if allow_missing:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "Chưa có bản rà soát nào cho bệnh nhân này."},
        )
    return rev


@router.patch("/reviews/{review_id}", response_model=ReviewResponse)
def patch_review(
    review_id: str,
    payload: PatchReviewRequest,
    repo: DemoRepository = Depends(get_demo_repository),
) -> ReviewResponse:
    try:
        return repo.patch_review(review_id, payload.expected_version, payload.sections, payload.edit_reason)
    except ReviewPolicyError as err:
        err_code = str(err)
        status_c = 409 if err_code in ("VERSION_CONFLICT", "INVALID_TRANSITION") else 422
        raise HTTPException(
            status_code=status_c,
            detail={"code": err_code, "message": f"Không thể cập nhật bản rà soát: {err_code}"},
        )
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": f"Không tìm thấy bản rà soát {review_id}."},
        )


@router.post("/reviews/{review_id}/approve", response_model=ReviewResponse)
def approve_review(
    review_id: str,
    payload: ApproveReviewRequest,
    repo: DemoRepository = Depends(get_demo_repository),
) -> ReviewResponse:
    try:
        return repo.approve_review(
            review_id, payload.review_version_id, payload.expected_version, payload.clinician_confirmation
        )
    except ReviewPolicyError as err:
        err_code = str(err)
        raise HTTPException(
            status_code=409,
            detail={"code": err_code, "message": f"Bác sĩ chưa thể duyệt bản rà soát: {err_code}"},
        )
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": f"Không tìm thấy bản rà soát {review_id}."},
        )


@router.post("/reviews/{review_id}/reject", response_model=ReviewResponse)
def reject_review(
    review_id: str,
    payload: RejectReviewRequest,
    repo: DemoRepository = Depends(get_demo_repository),
) -> ReviewResponse:
    if len(payload.reason.strip()) < 3 or len(payload.reason) > 1000:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "Lý do từ chối phải dài từ 3 đến 1000 ký tự."},
        )

    try:
        return repo.reject_review(review_id, payload.expected_version, payload.reason)
    except ReviewPolicyError as err:
        raise HTTPException(
            status_code=409,
            detail={"code": str(err), "message": f"Không thể từ chối bản rà soát: {err}"},
        )
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": f"Không tìm thấy bản rà soát {review_id}."},
        )


@router.get("/reviews/{review_id}/versions", response_model=VersionListResponse)
def list_review_versions(
    review_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repo: DemoRepository = Depends(get_demo_repository),
) -> VersionListResponse:
    items = repo.list_review_versions(review_id)
    total = len(items)
    start = (page - 1) * page_size
    return VersionListResponse(items=items[start:start + page_size], page=page, page_size=page_size, total=total)


@router.get("/reviews/{review_id}/export.pdf")
def export_pdf(
    review_id: str,
    review_version_id: str = Query(...),
    repo: DemoRepository = Depends(get_demo_repository),
) -> Response:
    patient_id = review_id.replace("rev_", "")
    rev = repo.get_review(patient_id, review_version_id=review_version_id)

    if not rev or rev.status != "approved":
        raise HTTPException(
            status_code=409,
            detail={"code": "EXPORT_NOT_ALLOWED", "message": "Chỉ có thể xuất PDF từ phiên bản đã duyệt."},
        )

    patient = repo.get_patient(patient_id)

    try:
        from src.clinical.pdf_generator import generate_review_pdf

        pdf_content = generate_review_pdf(rev, patient)
    except ModuleNotFoundError as exc:
        logger.exception("PDF export dependency is unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PDF_SERVICE_UNAVAILABLE",
                "message": "Dịch vụ xuất PDF chưa sẵn sàng. Vui lòng khởi động lại backend hoặc liên hệ quản trị viên.",
            },
        ) from exc
    except Exception as exc:
        logger.exception("PDF generation failed for review {}", review_version_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "PDF_GENERATION_FAILED",
                "message": "Không thể tạo file PDF cho phiên bản đã duyệt. Vui lòng thử lại.",
            },
        ) from exc

    filename = f"Tom_tat_dieu_tri_{patient_id}_v{rev.version}.pdf"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Content-Checksum": f"sha256:{review_version_id}",
        "X-Review-Version-ID": review_version_id,
    }
    return Response(content=pdf_content, media_type="application/pdf", headers=headers)
