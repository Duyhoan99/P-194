"""OCR verification REST endpoints adhering strictly to API_CONTRACT.md section 4.5."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from src.api.dependencies import get_demo_repository
from src.clinical.canonical import VerificationItem
from src.clinical.demo_repository import DemoRepository

router = APIRouter(tags=["ocr"])


class VerificationListResponse(BaseModel):
    items: list[VerificationItem]
    page: int
    page_size: int
    total: int


class PatchVerificationRequest(BaseModel):
    decision: str  # verified | dismissed
    corrected_text: str | None = None
    expected_version: int = 1


class DocumentPageResponse(BaseModel):
    document_id: str
    page_number: int
    image_url: str
    width: int = 2480
    height: int = 3508
    blocks: list[dict] = Field(default_factory=list)


@router.get("/patients/{patient_id}/verification-items", response_model=VerificationListResponse)
def get_verification_items(
    patient_id: str,
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repo: DemoRepository = Depends(get_demo_repository),
) -> VerificationListResponse:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    items, total = repo.list_verification_items(patient_id, status, page, page_size)
    return VerificationListResponse(items=items, page=page, page_size=page_size, total=total)


@router.patch("/verification-items/{verification_item_id}", response_model=VerificationItem)
def patch_verification_item(
    verification_item_id: str,
    payload: PatchVerificationRequest,
    repo: DemoRepository = Depends(get_demo_repository),
) -> VerificationItem:
    try:
        item, new_wm = repo.update_verification_item(verification_item_id, payload.decision, payload.corrected_text)
        return item
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": f"Không tìm thấy item xác minh {verification_item_id}."},
        )


@router.get("/documents/{document_id}/pages/{page_number}", response_model=None)
def get_document_page(
    document_id: str,
    page_number: int,
    representation: str = Query(default="image"),
) -> Response | DocumentPageResponse:

    if representation == "json":
        return DocumentPageResponse(
            document_id=document_id,
            page_number=page_number,
            image_url=f"/api/v1/documents/{document_id}/pages/{page_number}?representation=image",
            width=2480,
            height=3508,
            blocks=[],
        )

    # Return 1x1 transparent PNG fallback for image representation
    transparent_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        b"\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xafA4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return Response(content=transparent_png, media_type="image/png")
