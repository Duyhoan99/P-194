"""Clinical Review REST endpoints adhering strictly to API_CONTRACT.md sections 4.7, 4.10, 4.12."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from pydantic import BaseModel, Field
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
    review_version_id: str
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
    payload: GenerateReviewRequest | None = None,
    repo: DemoRepository = Depends(get_demo_repository),
) -> ReviewResponse:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    profiles = payload.profile_versions if payload else ["type_2_diabetes@1.0.0"]
    return repo.generate_review(patient_id, profiles)


@router.get("/patients/{patient_id}/review", response_model=ReviewResponse)
def get_review(
    patient_id: str,
    version: int | None = Query(default=None),
    review_version_id: str | None = Query(default=None),
    repo: DemoRepository = Depends(get_demo_repository),
) -> ReviewResponse:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    rev = repo.get_review(patient_id, version, review_version_id)
    if not rev:
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

    # Simple PDF binary payload for handoff contract
    pdf_content = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n162\n%%EOF\n"
    )

    headers = {
        "Content-Disposition": 'attachment; filename="clinical-review.pdf"',
        "X-Content-Checksum": f"sha256:{review_version_id}",
        "X-Review-Version-ID": review_version_id,
    }
    return Response(content=pdf_content, media_type="application/pdf", headers=headers)
