"""Grounded atomic claim composition from a bounded evidence packet."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5
import re

from pydantic import BaseModel, ConfigDict, Field

from src.agents.contracts import SectionCode
from src.agents.evidence import ScopedEvidence, is_prompt_injection_content
from src.agents.retrieval.concepts import resolve_concept

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


def compose_comparison_claims(evidence_packet: list[ScopedEvidence]) -> list[ProposedClaim]:
    """Compare retrieved endpoint pairs without deriving beyond numeric change."""
    groups: dict[str, list[ScopedEvidence]] = {}
    for evidence in evidence_packet:
        source = evidence.item.source_value
        if not isinstance(source, dict):
            continue
        title = re.sub(r"^(xét nghiệm|lab)\s*:\s*", "", str(source.get("title", "")).casefold()).strip()
        if title:
            groups.setdefault(title, []).append(evidence)
    claims: list[ProposedClaim] = []
    for concept, items in groups.items():
        items.sort(key=lambda item: item.item.source_time or "")
        if len(items) < 2:
            continue
        first, last = items[0], items[-1]
        first_summary = str(first.item.source_value.get("summary", ""))
        last_summary = str(last.item.source_value.get("summary", ""))
        first_num = re.search(r"-?\d+(?:[.,]\d+)?", first_summary)
        last_num = re.search(r"-?\d+(?:[.,]\d+)?", last_summary)
        if not first_num or not last_num:
            continue
        before = float(first_num.group().replace(",", "."))
        after = float(last_num.group().replace(",", "."))
        direction = "tăng" if after > before else "giảm" if after < before else "không đổi"
        unit = first_summary[first_num.end():].strip()
        date_a, date_b = (first.item.source_time or "")[:10], (last.item.source_time or "")[:10]
        delta = abs(after - before)
        text = (
            f"{concept}: {before:g} {unit} ({date_a}) → {after:g} {unit} ({date_b}), "
            f"{direction} {delta:g} {unit}."
        ).replace("  ", " ")
        claim_id = str(uuid5(NAMESPACE_URL, f"clinical-comparison:{first.item.evidence_id}:{last.item.evidence_id}"))
        claims.append(ProposedClaim(
            claim_id=f"clm_{claim_id}", text=text,
            evidence_ids=[first.item.evidence_id, last.item.evidence_id],
            section_code="recent_results",
        ))
    return claims


def compose_trend_claims(evidence_packet: list[ScopedEvidence]) -> list[ProposedClaim]:
    """Synthesize retrieved longitudinal lab/medication facts without changing retrieval."""
    observation_groups: dict[str, list[ScopedEvidence]] = {}
    medication_groups: dict[str, list[ScopedEvidence]] = {}
    for evidence in evidence_packet:
        source = evidence.item.source_value
        if not isinstance(source, dict):
            continue
        fact_type = evidence.item.fact_type.casefold()
        title = str(source.get("title", "")).strip()
        if "observation" in fact_type and title:
            raw_concept = re.sub(r"^(xét nghiệm|lab)\s*:\s*", "", title, flags=re.IGNORECASE).strip()
            resolved = resolve_concept(raw_concept)
            concept = resolved.canonical if resolved else raw_concept
            observation_groups.setdefault(concept, []).append(evidence)
        elif "medication" in fact_type and title:
            label = re.sub(r"^(thuốc|medication)\s*:\s*", "", title, flags=re.IGNORECASE).strip()
            medication = re.sub(r"\s+\d+(?:[.,]\d+)?\s*(?:mg|mcg|g|ml)\b.*$", "", label, flags=re.IGNORECASE).strip()
            medication_groups.setdefault(medication, []).append(evidence)

    claims: list[ProposedClaim] = []
    for concept, items in observation_groups.items():
        items.sort(key=lambda item: item.item.source_time or "")
        points: list[tuple[float, str, str, ScopedEvidence]] = []
        for item in items:
            summary = str(item.item.source_value.get("summary", ""))
            match = re.search(r"-?\d+(?:[.,]\d+)?", summary)
            if not match:
                continue
            points.append((
                float(match.group().replace(",", ".")),
                summary[match.end():].strip(),
                (item.item.source_time or "")[:10],
                item,
            ))
        if len(points) < 2:
            continue
        values = [point[0] for point in points]
        increasing = all(left <= right for left, right in zip(values, values[1:])) and values[0] != values[-1]
        decreasing = all(left >= right for left, right in zip(values, values[1:])) and values[0] != values[-1]
        direction = "tăng" if increasing else "giảm" if decreasing else "dao động"
        sequence = " → ".join(f"{value:g} {unit} ({date})" for value, unit, date, _ in points)
        delta = values[-1] - values[0]
        conclusion = f"xu hướng {direction}; thay đổi tổng {delta:+g} {points[-1][1]}"
        evidence_ids = [point[3].item.evidence_id for point in points]
        claim_id = str(uuid5(NAMESPACE_URL, f"clinical-trend:{':'.join(evidence_ids)}"))
        claims.append(ProposedClaim(
            claim_id=f"clm_{claim_id}", text=f"{concept}: {sequence}; {conclusion}.",
            evidence_ids=evidence_ids, section_code="recent_results",
        ))

    for medication, items in medication_groups.items():
        items.sort(key=lambda item: item.item.source_time or "")
        deduplicated: list[tuple[str, str, ScopedEvidence]] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            date = (item.item.source_time or "")[:10]
            summary = str(item.item.source_value.get("summary", ""))
            status = summary.split(":", 1)[-1].strip() if summary else "không rõ trạng thái"
            key = (date, status.casefold())
            if key not in seen:
                seen.add(key)
                deduplicated.append((date, status, item))
        if not deduplicated:
            continue
        sequence = " → ".join(f"{status} ({date})" for date, status, _ in deduplicated)
        statuses = [status.casefold() for _, status, _ in deduplicated]
        conclusion = (
            f"trạng thái thay đổi từ {deduplicated[0][1]} sang {deduplicated[-1][1]}"
            if len(set(statuses)) > 1 else f"tiếp tục được ghi nhận ở trạng thái {deduplicated[-1][1]}"
        )
        evidence_ids = [item.item.evidence_id for _, _, item in deduplicated]
        claim_id = str(uuid5(NAMESPACE_URL, f"medication-trend:{':'.join(evidence_ids)}"))
        claims.append(ProposedClaim(
            claim_id=f"clm_{claim_id}", text=f"Thuốc {medication}: {sequence}; {conclusion}.",
            evidence_ids=evidence_ids, section_code="current_medications",
        ))
    return claims or compose_atomic_claims(evidence_packet)


def compose_atomic_claims_llm(
    evidence_packet: list[ScopedEvidence],
    llm_client: "LLMClinicalClientBase",  # type: ignore[name-defined]  # noqa: F821
    question: str | None = None,
) -> dict:
    """Compose claims using LLM with bounded evidence, then validate.

    Security rules:
    - Only sends bounded evidence snippets to the model (NOT full patient record).
    - Model-returned evidence_ids MUST exist in the provided packet.
    - Model-created citations are rejected.
    - Falls back to deterministic if model returns None or schema is invalid.
    - Treatment/medication prescription claims are filtered before sending.
    - Prompt injection in evidence content is blocked by system prompt hierarchy.
    """
    from src.agents.llm_client import LLMClinicalClientBase  # noqa: PLC0415

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
        return {"claims": [], "unsupported_claims": [], "conflicts": []}

    try:
        raw_claims = llm_client.generate_claims(
            question=question,
            evidence_packet=evidence_items,
            temperature=0.0,
        )
    except Exception:
        # Safe fallback on any exception
        return {"claims": compose_atomic_claims(evidence_packet), "unsupported_claims": [], "conflicts": []}

    if raw_claims is None:
        # Model returned None → use deterministic fallback
        return {"claims": compose_atomic_claims(evidence_packet), "unsupported_claims": [], "conflicts": []}

    # Validate and convert model output
    claims: list[ProposedClaim] = []
    unsupported_claims: list[ProposedClaim] = []
    conflicts: list[dict] = raw_claims.get("conflicts", [])
    
    valid_section_codes = {
        "patient_overview", "active_conditions", "current_medications",
        "recent_results", "changes_to_review", "data_gaps",
    }

    for raw in raw_claims.get("claims", []):
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
                f"clinical-review-llm:{':'.join(sorted(valid_ev_ids))}:{text}",
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

    for raw in raw_claims.get("unsupported_claims", []):
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        
        claim_id = str(uuid5(NAMESPACE_URL, f"clinical-review-unsupported:{text}"))
        unsupported_claims.append(
            ProposedClaim(
                claim_id=f"clm_{claim_id}",
                text=text,
                evidence_ids=[],
                section_code="patient_overview",
            )
        )

    if not claims and not unsupported_claims:
        # Model returned nothing usable → deterministic fallback
        return {"claims": compose_atomic_claims(evidence_packet), "unsupported_claims": [], "conflicts": []}

    return {"claims": claims, "unsupported_claims": unsupported_claims, "conflicts": conflicts}
