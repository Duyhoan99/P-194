from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.agents.contracts import DocumentCitation, EvidenceItem


class StructuredFact(BaseModel):
    """
    A strictly typed schema representing an extracted clinical fact.
    Replaces loose dictionaries to ensure validation before persistence.
    """
    model_config = ConfigDict(extra="ignore")

    fact_id: str = Field(..., description="Unique identifier for this fact")
    patient_id: str = Field(..., description="The patient this fact belongs to")
    fact_type: str = Field(..., description="e.g., 'lab_result', 'diagnosis', 'medication'")

    canonical_code: str | None = Field(default=None, description="Standardized code or name, e.g., LOINC or SNOMED")

    value: Any = Field(..., description="The extracted value, can be a number, string, or structured object")
    unit: str | None = Field(default=None, description="Unit of measurement if applicable")

    event_time: datetime | None = Field(default=None, description="When the clinical event actually occurred")
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="When the system recorded this fact")

    source_document_id: str | None = Field(default=None, description="ID of the document this was extracted from")
    page: int | None = Field(default=None, description="Page number in the document")
    evidence_text: str | None = Field(default=None, description="The exact raw text this was extracted from")

    confidence: float | None = Field(default=None, description="Confidence score from OCR/Extraction engine")
    verification_status: Literal["verified", "needs_verification", "rejected"] = Field(default="needs_verification")

    def to_evidence_item(self) -> EvidenceItem:
        """
        Adapter to convert StructuredFact into the older EvidenceItem format
        used by the LangGraph agents and legacy code.
        """
        citations = []
        if self.source_document_id:
            citations.append(
                DocumentCitation(
                    source_type="document",
                    document_id=self.source_document_id,
                    page_number=self.page,
                    snippet=self.evidence_text or "",
                )
            )

        # Normalize the value string combining unit if present
        norm_val = str(self.value)
        if self.unit:
            norm_val += f" {self.unit}"

        return EvidenceItem(
            evidence_id=self.fact_id,
            fact_type=self.fact_type,
            normalized_value=norm_val,
            source_value=str(self.value),
            source_time=self.event_time.isoformat() if self.event_time else None,
            verification_status="verified" if self.verification_status == "verified" else "needs_verification",
            citations=citations
        )
