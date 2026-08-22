"""OCR verification REST endpoints adhering strictly to API_CONTRACT.md section 4.5."""

import json
import pathlib
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from src.api.dependencies import get_demo_repository
from src.clinical.canonical import VerificationItem
from src.clinical.demo_repository import DemoRepository

router = APIRouter(tags=["ocr"])

# Reference to the same IngestionService used by ingestion_routes
# (imported lazily to avoid circular imports)
_DEMO_DATA_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "demo_mvp_v1"
_DEMO_DOCS_DIR = _DEMO_DATA_DIR / "documents"
_DEMO_MANIFEST = _DEMO_DATA_DIR / "dataset_manifest.json"


@lru_cache(maxsize=1)
def _demo_document_index() -> dict[str, pathlib.Path]:
    """Resolve stable demo document IDs from the authoritative manifest."""
    if not _DEMO_MANIFEST.is_file():
        return {}
    try:
        manifest = json.loads(_DEMO_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    data_root = _DEMO_DATA_DIR.resolve()
    index: dict[str, pathlib.Path] = {}
    for item in manifest.get("documents", []):
        if not isinstance(item, dict):
            continue
        document_id = str(item.get("document_id") or "").strip()
        relative_file = str(item.get("file") or "").strip()
        if not document_id or not relative_file:
            continue
        file_path = (_DEMO_DATA_DIR / relative_file).resolve()
        if data_root not in file_path.parents or not file_path.is_file():
            continue
        index[document_id.casefold()] = file_path
    return index


def _inline_file_response(file_path: pathlib.Path) -> Response:
    media_type = "application/pdf" if file_path.suffix.casefold() == ".pdf" else "application/octet-stream"
    return Response(
        content=file_path.read_bytes(),
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{file_path.name}"',
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


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


@router.get("/documents/{document_id}/raw", response_model=None)
def get_document_raw(document_id: str) -> Response:
    """Serve the raw PDF file for in-browser viewing.

    First checks the in-memory IngestionService DocumentStore.
    Falls back to demo files on disk matching the document_id pattern.
    """
    # 1. Try in-memory DocumentStore (for uploaded documents)
    from src.api.ingestion_routes import _ingestion_service
    stored = _ingestion_service.document_store.get(document_id)
    if stored and stored.content:
        name_lower = stored.document_name.lower()
        media_type = "application/pdf"
        if name_lower.endswith(".png"):
            media_type = "image/png"
        elif name_lower.endswith(".jpg") or name_lower.endswith(".jpeg"):
            media_type = "image/jpeg"
        elif name_lower.endswith(".json"):
            media_type = "application/json"

        return Response(
            content=stored.content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'inline; filename="{stored.document_name}"',
                "Cache-Control": "public, max-age=3600",
            },
        )

    # 2. Resolve fixture documents by their stable manifest ID. Do not select
    # the first file sharing a patient prefix: that can display the wrong source.
    manifest_file = _demo_document_index().get(document_id.casefold())
    if manifest_file:
        return _inline_file_response(manifest_file)

    # 3. Compatibility fallback for a legacy ID that is already the exact file
    # stem. This remains exact-only and cannot escape the demo document folder.
    if _DEMO_DOCS_DIR.is_dir():
        cleaned = document_id.removeprefix("DOC-")
        for pdf_file in _DEMO_DOCS_DIR.glob("*.pdf"):
            if pdf_file.stem.casefold() == cleaned.casefold():
                return _inline_file_response(pdf_file)

    raise HTTPException(
        status_code=404,
        detail={"code": "RESOURCE_NOT_FOUND", "message": f"Không tìm thấy tài liệu {document_id}."},
    )
