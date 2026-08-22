"""Claims and Evidence REST endpoints adhering strictly to API_CONTRACT.md section 4.9."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.clinical.canonical import Citation, FhirCitation

router = APIRouter(tags=["claims"])


class ClaimEvidenceResponse(BaseModel):
    claim_id: str
    claim_text: str
    claim_status: str
    evidence: list[Citation] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    rating: str  # correct | incorrect | irrelevant
    comment: str | None = None


class FeedbackResponse(BaseModel):
    feedback_id: str
    claim_id: str
    rating: str
    created_at: str


@router.get("/claims/{claim_id}/evidence", response_model=ClaimEvidenceResponse)
def get_claim_evidence(claim_id: str) -> ClaimEvidenceResponse:
    default_cit = FhirCitation(
        citation_id=f"cit_{claim_id}",
        document_id="DOC-001",
        resource_type="Observation",
        resource_id="res_001",
        snippet="HbA1c: 8.7%",
        source_checksum="sha256:baseline",
    )
    return ClaimEvidenceResponse(
        claim_id=claim_id,
        claim_text="HbA1c tăng từ 7,5% lên 8,7%.",
        claim_status="verified",
        evidence=[default_cit],
    )


@router.post("/claims/{claim_id}/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(claim_id: str, payload: FeedbackRequest) -> FeedbackResponse:
    if payload.rating not in ("correct", "incorrect", "irrelevant"):
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "Rating phải là correct, incorrect, hoặc irrelevant."},
        )

    return FeedbackResponse(
        feedback_id=f"fb_{claim_id}_01",
        claim_id=claim_id,
        rating=payload.rating,
        created_at=datetime.now().isoformat(),
    )
