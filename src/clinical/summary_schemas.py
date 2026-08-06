"""Evidence-first contracts for deterministic clinical summary drafts."""

from typing import Literal
from uuid import UUID

# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

from src.clinical.schemas import SourceLineage

SUMMARY_SECTIONS = (
    "Clinical Overview",
    "Active Problems",
    "Current and Recent Medications",
    "Key Timeline",
    "Laboratory Trends",
    "Conflicts and Missing Information",
    "Limitations",
)


class Citation(BaseModel):
    citation_id: str
    lineage: SourceLineage
    supported_fields: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    claim_id: str
    section: str
    text: str
    citation_ids: list[str] = Field(default_factory=list)
    status: Literal["VALID", "INVALID", "UNSUPPORTED"]


class Conflict(BaseModel):
    conflict_id: str
    topic: str
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["UNRESOLVED", "RESOLVED"]
    resolution_note: str | None = None
    resolved_by: str | None = None


class ClinicalSummaryDraft(BaseModel):
    summary_id: UUID
    subject_id: int
    hadm_id: int | None = None
    stay_id: int | None = None
    status: Literal["DRAFT", "NEEDS_REVISION", "REJECTED", "APPROVED", "EXPORTED"]
    sections: dict[str, list[Claim]]
    citations: list[Citation]
    conflicts: list[Conflict]
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str]
    trace_id: str


class ValidationIssue(BaseModel):
    code: str
    claim_id: str | None = None
    message: str


class ValidationReport(BaseModel):
    valid: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
