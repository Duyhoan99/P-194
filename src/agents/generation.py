"""Grounded atomic claim composition from a bounded evidence packet."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

from src.agents.contracts import SectionCode
from src.agents.evidence import ScopedEvidence, is_prompt_injection_content

GENERATOR_VERSION = "wp2-grounded@1.0.0"


class ProposedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    section_code: SectionCode


_SECTION_BY_FACT_TYPE: tuple[tuple[str, SectionCode], ...] = (
    ("condition", "active_conditions"),
    ("allergy", "active_conditions"),
    ("medication", "current_medications"),
    ("trend", "recent_results"),
    ("observation", "recent_results"),
    ("lab", "recent_results"),
    ("gap", "data_gaps"),
    ("conflict", "changes_to_review"),
    ("change", "changes_to_review"),
)


def _statement(evidence: ScopedEvidence) -> str | None:
    value = evidence.item.normalized_value
    if isinstance(value, dict):
        for key in ("statement", "public_text", "answer"):
            statement = value.get(key)
            if isinstance(statement, str) and statement.strip():
                return statement.strip()
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _section(evidence: ScopedEvidence) -> SectionCode:
    value = evidence.item.normalized_value
    if isinstance(value, dict) and value.get("section_code") in {
        "patient_overview",
        "active_conditions",
        "current_medications",
        "recent_results",
        "changes_to_review",
        "data_gaps",
    }:
        return value["section_code"]
    fact_type = evidence.item.fact_type.casefold()
    for marker, section in _SECTION_BY_FACT_TYPE:
        if marker in fact_type:
            return section
    return "patient_overview"


def compose_atomic_claims(evidence_packet: list[ScopedEvidence]) -> list[ProposedClaim]:
    """Copy backend-supplied factual statements; never derive clinical values."""
    claims: list[ProposedClaim] = []
    for evidence in evidence_packet:
        if is_prompt_injection_content(evidence.item):
            continue
        statement = _statement(evidence)
        if not statement:
            continue
        claim_id = str(
            uuid5(
                NAMESPACE_URL,
                f"clinical-review:{evidence.patient_id}:{evidence.item.evidence_id}:{statement}",
            )
        )
        claims.append(
            ProposedClaim(
                claim_id=f"clm_{claim_id}",
                text=statement,
                evidence_ids=[evidence.item.evidence_id],
                section_code=_section(evidence),
            )
        )
    return claims
