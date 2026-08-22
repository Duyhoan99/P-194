"""OCR verification service and storage according to API_CONTRACT.md section 4.5."""

import uuid

from src.clinical.canonical import VerificationItem


class OCRVerificationService:
    """Manages OCR verification items and clinician corrections."""

    def __init__(self):
        self._items: dict[str, VerificationItem] = {}

    def add_verification_item(
        self,
        document_id: str,
        page_number: int,
        extracted_text: str,
        confidence: float,
        block_id: str | None = None,
        bbox: list[float] | None = None,
        engine: str = "paddleocr",
        engine_version: str = "3.0.0",
    ) -> VerificationItem:
        item_id = f"ver_{uuid.uuid4().hex[:8]}"
        item = VerificationItem(
            verification_item_id=item_id,
            document_id=document_id,
            page_number=page_number,
            block_id=block_id,
            bbox=bbox,
            extracted_text=extracted_text,
            corrected_text=None,
            confidence=confidence,
            status="pending",
            engine=engine,
            engine_version=engine_version,
        )
        self._items[item_id] = item
        return item

    def get_item(self, item_id: str) -> VerificationItem | None:
        return self._items.get(item_id)

    def list_items(
        self,
        document_ids: list[str] | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[VerificationItem], int]:
        filtered = list(self._items.values())
        if document_ids is not None:
            filtered = [item for item in filtered if item.document_id in document_ids]
        if status:
            filtered = [item for item in filtered if item.status == status]

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end], total

    def update_decision(
        self,
        item_id: str,
        decision: str,  # 'verified' or 'dismissed'
        corrected_text: str | None = None,
    ) -> VerificationItem:
        item = self._items.get(item_id)
        if not item:
            raise KeyError(f"Verification item {item_id} not found")

        item.status = decision  # type: ignore
        if corrected_text is not None:
            item.corrected_text = corrected_text
        return item
