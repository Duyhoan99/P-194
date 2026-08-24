"""Canonical domain models, citations, and provenance schemas according to API_CONTRACT.md."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class SourceReference(BaseModel):
    source_type: Literal["pdf", "fhir", "canonical_record", "rule"]
    source_record_id: str
    source_time: str | None = None


class DocumentCitation(BaseModel):
    citation_id: str
    source_type: Literal["pdf", "ocr"] = "pdf"
    document_id: str
    document_name: str
    page_number: int
    block_id: str | None = None
    table_id: str | None = None
    bbox: list[float] | None = None
    char_start: int | None = None
    char_end: int | None = None
    snippet: str
    source_checksum: str
    extraction_version: str = "1.0.0"
    ocr_confidence: float | None = None


class FhirCitation(BaseModel):
    citation_id: str
    source_type: Literal["fhir"] = "fhir"
    document_id: str
    resource_type: str
    resource_id: str
    json_pointer: str | None = None
    snippet: str
    source_checksum: str


class RecordCitation(BaseModel):
    citation_id: str
    source_type: Literal["canonical_record", "rule"] = "canonical_record"
    source_record_id: str
    source_time: str | None = None
    snippet: str
    rule_version: str | None = None


Citation = DocumentCitation | FhirCitation | RecordCitation


class VerifiedClaim(BaseModel):
    claim_id: str
    text: str
    status: Literal["verified", "needs_verification", "unsupported", "invalid"]
    confidence: Literal["high", "medium", "low"] | None = "high"
    citations: list[Citation] = Field(default_factory=list)
    generator_version: str = "1.0.0"


class VerificationItem(BaseModel):
    verification_item_id: str
    document_id: str
    page_number: int
    block_id: str | None = None
    bbox: list[float] | None = None
    extracted_text: str
    corrected_text: str | None = None
    confidence: float
    status: Literal["pending", "verified", "dismissed"] = "pending"
    engine: str = "paddleocr"
    engine_version: str = "3.0.0"


class ReferenceRange(BaseModel):
    low: float | None = None
    high: float | None = None


class TrendPoint(BaseModel):
    observed_at: str
    value: float
    unit: str
    raw_value: float | None = None
    raw_unit: str | None = None
    calculation: dict[str, Any] | None = None
    reference_range: ReferenceRange | None = None
    citations: list[Citation] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    event_id: str
    event_type: Literal["encounter", "observation", "medication", "condition", "allergy", "note"]
    occurred_at: str
    title: str
    summary: str
    citations: list[Citation] = Field(default_factory=list)


class ConflictFlag(BaseModel):
    conflict_id: str
    conflict_type: str
    description: str
    status: Literal["open", "reviewed", "resolved"] = "open"
    source_a: list[Citation] = Field(default_factory=list)
    source_b: list[Citation] = Field(default_factory=list)


class DrugInteractionFlag(BaseModel):
    flag_id: str
    ingredients: list[str]
    severity: Literal["low", "moderate", "high", "unknown"]
    description: str
    rule_source: str
    rule_version: str
    status: Literal["open", "reviewed", "not_applicable", "superseded"] = "open"
    citations: list[Citation] = Field(default_factory=list)


class DataQualityFlag(BaseModel):
    flag_id: str
    code: str
    severity: Literal["info", "warning", "blocking"]
    message: str
    status: Literal["open", "verified", "dismissed"] = "open"
    verification_item_id: str | None = None


class ReviewSection(BaseModel):
    section_code: Literal[
        "patient_overview",
        "active_conditions",
        "current_medications",
        "recent_results",
        "changes_to_review",
        "data_gaps",
    ]
    title: str
    claims: list[VerifiedClaim] = Field(default_factory=list)
    clinician_text: str | None = None


class Coverage(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    encounter_count: int = 0


class ReviewResponse(BaseModel):
    review_id: str
    review_version_id: str
    patient_id: str
    status: Literal["generated", "under_review", "edited", "approved", "rejected", "stale"]
    version: int
    generated_at: str
    updated_at: str
    approved_at: str | None = None
    data_watermark: str
    is_current_watermark: bool = True
    profile_versions: list[str] = Field(default_factory=list)
    coverage: Coverage
    sections: list[ReviewSection] = Field(default_factory=list)
    conflicts: list[ConflictFlag] = Field(default_factory=list)
    drug_interactions: list[DrugInteractionFlag] = Field(default_factory=list)
    data_quality_flags: list[DataQualityFlag] = Field(default_factory=list)
    disclaimer: str = "Tài liệu chỉ phục vụ rà soát lâm sàng. Bác sĩ chịu trách nhiệm cho mọi quyết định điều trị."
    clinician_confirmation: bool | None = None
    memory_version_used: int | None = None


class PatientSummary(BaseModel):
    patient_id: str
    pseudonym: str
    age: int | None = None
    sex: Literal["male", "female", "other", "unknown"]
    primary_condition: str | None = None
    last_encounter_at: str | None = None
    latest_data_watermark: str | None = None


class UserMe(BaseModel):
    user_id: str
    display_name: str
    tenant_id: str
    roles: list[Literal["clinician", "administrator", "auditor"]]
    permissions: list[str]


class MemoryItem(BaseModel):
    item_id: str
    category: str
    text: str
    citations: list[Citation] = Field(default_factory=list)


class PatientMemory(BaseModel):
    memory_version_id: str
    version: int
    patient_id: str
    source_review_version_id: str
    items: list[MemoryItem] = Field(default_factory=list)
    approved_by: str
    approved_at: str
