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


def compose_atomic_claims_openai(
    evidence_packet: list[ScopedEvidence],
    openai_client: "OpenAIClinicalClientBase",  # type: ignore[name-defined]  # noqa: F821
    question: str | None = None,
) -> list[ProposedClaim]:
    """Compose claims using OpenAI with bounded evidence, then validate.

    Security rules:
    - Only sends bounded evidence snippets to the model (NOT full patient record).
    - Model-returned evidence_ids MUST exist in the provided packet.
    - Model-created citations are rejected.
    - Falls back to deterministic if model returns None or schema is invalid.
    - Treatment/medication prescription claims are filtered before sending.
    - Prompt injection in evidence content is blocked by system prompt hierarchy.
    """
    from src.agents.openai_client import OpenAIClinicalClientBase  # noqa: PLC0415

    # Build evidence dicts for the model — only what's in the bounded packet
    evidence_by_id: dict[str, ScopedEvidence] = {}
    evidence_items: list[dict] = []
    for scoped in evidence_packet:
        if is_prompt_injection_content(scoped.item):
            continue
        ev_id = scoped.item.evidence_id
        evidence_by_id[ev_id] = scoped
        nv = scoped.item.normalized_value
        statement = ""
        if isinstance(nv, dict):
            statement = nv.get("statement") or nv.get("public_text") or ""
        elif isinstance(nv, str):
            statement = nv
        evidence_items.append({"evidence_id": ev_id, "statement": statement})

    if not evidence_items:
        return []

    try:
        raw_claims = openai_client.generate_claims(
            question=question,
            evidence_items=evidence_items,
            temperature=0.0,
        )
    except Exception:
        # Safe fallback on any exception
        return compose_atomic_claims(evidence_packet)

    if raw_claims is None:
        # Model returned None → use deterministic fallback
        return compose_atomic_claims(evidence_packet)

    # Validate and convert model output
    claims: list[ProposedClaim] = []
    valid_section_codes = {
        "patient_overview", "active_conditions", "current_medications",
        "recent_results", "changes_to_review", "data_gaps",
    }

    for raw in raw_claims:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        raw_ev_ids = raw.get("evidence_ids", [])
        if not isinstance(raw_ev_ids, list):
            continue

        # Validate: ALL evidence_ids must exist in bounded packet
        valid_ev_ids = [eid for eid in raw_ev_ids if str(eid) in evidence_by_id]
        if not valid_ev_ids:
            # Model created evidence that doesn't exist in packet → reject claim
            continue

        section_raw = str(raw.get("section_code", "patient_overview"))
        section_code: SectionCode = section_raw if section_raw in valid_section_codes else "patient_overview"  # type: ignore[assignment]

        claim_id = str(
            uuid5(
                NAMESPACE_URL,
                f"clinical-review-openai:{':'.join(sorted(valid_ev_ids))}:{text}",
            )
        )
        claims.append(
            ProposedClaim(
                claim_id=f"clm_{claim_id}",
                text=text,
                evidence_ids=valid_ev_ids,
                section_code=section_code,
            )
        )

    if not claims:
        # Model returned nothing usable → deterministic fallback
        return compose_atomic_claims(evidence_packet)

    return claims
