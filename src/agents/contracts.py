"""Contract-faithful models for the backend-to-agent boundary.

The public shapes in this module mirror ``API_CONTRACT.md``.  Internal graph
metadata lives in :mod:`src.agents.state` and is never serialized as an
``AgentResult``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentCitation(_ContractModel):
    citation_id: str
    source_type: Literal["pdf"]
    document_id: str
    document_name: str
    page_number: int = Field(ge=1)
    block_id: str | None = None
    table_id: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    snippet: str
    source_checksum: str
    extraction_version: str
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)


class FhirCitation(_ContractModel):
    citation_id: str
    source_type: Literal["fhir"]
    document_id: str
    resource_type: str
    resource_id: str
    json_pointer: str | None = None
    snippet: str
    source_checksum: str


class RecordCitation(_ContractModel):
    citation_id: str
    source_type: Literal["canonical_record", "rule"]
    source_record_id: str
    source_time: str | None = None
    snippet: str
    rule_version: str | None = None


Citation = Annotated[
    DocumentCitation | FhirCitation | RecordCitation,
    Field(discriminator="source_type"),
]


class EvidenceItem(_ContractModel):
    evidence_id: str
    fact_type: str
    normalized_value: Any
    source_value: Any
    source_time: str | None
    verification_status: Literal["verified", "needs_verification"]
    citations: list[Citation]


class AgentRequest(_ContractModel):
    request_id: str
    task_type: Literal["review_generation", "ask_chart"]
    tenant_id: str
    patient_id: str
    user_id: str
    data_watermark: str
    profile_versions: list[str]
    approved_memory: dict[str, Any] | None
    structured_facts: list[dict[str, Any]]
    note_evidence: list[EvidenceItem]
    question: str | None = None

    @model_validator(mode="after")
    def ask_chart_requires_question(self) -> AgentRequest:
        if self.task_type == "ask_chart" and not (self.question or "").strip():
            raise ValueError("ask_chart requires a non-empty question")
        return self


class VerifiedClaim(_ContractModel):
    claim_id: str
    text: str
    status: Literal["verified", "needs_verification", "unsupported", "invalid"]
    confidence: Literal["high", "medium", "low"] | None
    citations: list[Citation]
    generator_version: str

    @model_validator(mode="after")
    def verified_claim_requires_citation(self) -> VerifiedClaim:
        if self.status == "verified" and not self.citations:
            raise ValueError("verified claims require at least one citation")
        return self


SectionCode = Literal[
    "patient_overview",
    "active_conditions",
    "current_medications",
    "recent_results",
    "changes_to_review",
    "data_gaps",
]


class ReviewSection(_ContractModel):
    section_code: SectionCode
    title: str
    claims: list[VerifiedClaim]
    clinician_text: str | None = None


class AgentError(_ContractModel):
    code: str
    message: str


class AgentResult(_ContractModel):
    task_type: Literal["review_generation", "ask_chart"]
    status: Literal["answered", "not_found", "conflicting", "not_allowed", "error"]
    data_watermark: str
    sections: list[ReviewSection] | None = None
    answer: str | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    claims: list[VerifiedClaim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    errors: list[AgentError] = Field(default_factory=list)

    @model_validator(mode="after")
    def public_contract_is_consistent(self) -> AgentResult:
        public_claims = [claim for claim in self.claims if claim.status in {"verified", "needs_verification"}]
        if len(public_claims) != len(self.claims):
            raise ValueError("unsupported or invalid claims cannot appear in AgentResult")
        if self.task_type == "ask_chart" and self.sections is not None:
            raise ValueError("ask_chart cannot return review sections")
        return self
