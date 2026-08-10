"""Patient-scoped evidence packet adapters and bounded retrieval.

This module never opens source files or queries a database.  It consumes only
the already scoped ``AgentRequest`` supplied by the backend.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from src.agents.contracts import AgentRequest, Citation, EvidenceItem


class EvidenceScopeError(ValueError):
    """Raised when an evidence identifier belongs to another patient/tenant."""


@dataclass(frozen=True)
class ScopedEvidence:
    item: EvidenceItem
    origin: Literal["structured", "note"]
    patient_id: str
    tenant_id: str
    record_status: str | None = None


_PATIENT_TOKEN = re.compile(r"PAT-?\d{3}", re.IGNORECASE)
_INJECTION_PATTERNS = (
    "ignore previous",
    "ignore all previous",
    "bỏ qua hướng dẫn",
    "bo qua huong dan",
    "system prompt",
    "developer message",
    "hãy mở hồ sơ",
)
_STOPWORDS = {
    "bệnh",
    "bệnh nhân",
    "bao",
    "bao nhiêu",
    "có",
    "cho",
    "của",
    "được",
    "hồ sơ",
    "kết",
    "kết quả",
    "không",
    "là",
    "như",
    "nào",
    "nhiêu",
    "quả",
    "thế",
    "the",
    "patient",
    "what",
}


def _patient_tokens(value: str) -> set[str]:
    return {token.upper().replace("PAT", "PAT-").replace("--", "-") for token in _PATIENT_TOKEN.findall(value)}


def _citation_identifiers(citation: Citation) -> Iterable[str]:
    yield citation.citation_id
    if hasattr(citation, "document_id"):
        yield citation.document_id
    if hasattr(citation, "resource_id"):
        yield citation.resource_id
    if hasattr(citation, "source_record_id"):
        yield citation.source_record_id


def _scope_tokens(item: EvidenceItem) -> set[str]:
    tokens = _patient_tokens(item.evidence_id)
    for citation in item.citations:
        for identifier in _citation_identifiers(citation):
            tokens.update(_patient_tokens(identifier))
    return tokens


def _record_status(payload: dict[str, Any], item: EvidenceItem) -> str | None:
    direct = payload.get("record_status") or payload.get("status")
    if direct:
        return str(direct).casefold().replace("_", "-")
    if isinstance(item.normalized_value, dict):
        nested = item.normalized_value.get("record_status") or item.normalized_value.get("status")
        if nested:
            return str(nested).casefold().replace("_", "-")
    return None


def _to_evidence_item(payload: dict[str, Any]) -> EvidenceItem:
    fields = EvidenceItem.model_fields
    contract_payload = {key: payload[key] for key in fields if key in payload}
    return EvidenceItem.model_validate(contract_payload)


def build_scoped_evidence(request: AgentRequest) -> list[ScopedEvidence]:
    """Validate the complete packet before retrieval and fail closed on leakage."""
    packet: list[ScopedEvidence] = []
    for raw in request.structured_facts:
        item = _to_evidence_item(raw)
        patient_id = str(raw.get("patient_id", request.patient_id))
        tenant_id = str(raw.get("tenant_id", request.tenant_id))
        packet.append(
            ScopedEvidence(
                item=item,
                origin="structured",
                patient_id=patient_id,
                tenant_id=tenant_id,
                record_status=_record_status(raw, item),
            )
        )
    packet.extend(
        ScopedEvidence(
            item=item,
            origin="note",
            patient_id=request.patient_id,
            tenant_id=request.tenant_id,
            record_status=_record_status({}, item),
        )
        for item in request.note_evidence
    )

    for scoped in packet:
        if scoped.patient_id != request.patient_id or scoped.tenant_id != request.tenant_id:
            raise EvidenceScopeError("Evidence packet scope does not match the locked request scope.")
        tokens = _scope_tokens(scoped.item)
        if tokens and tokens != {request.patient_id.upper()}:
            raise EvidenceScopeError("Evidence packet contains a foreign patient identifier.")
    return packet


def is_prompt_injection_content(item: EvidenceItem) -> bool:
    """Detect untrusted instructions for telemetry/tests; never execute them."""
    content = f"{item.fact_type} {item.source_value} {item.normalized_value}".casefold()
    return any(pattern in content for pattern in _INJECTION_PATTERNS)


def _search_text(item: EvidenceItem) -> str:
    snippets = " ".join(citation.snippet for citation in item.citations)
    return f"{item.fact_type} {item.normalized_value} {item.source_value} {snippets}".casefold()


def _terms(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[\w%/.+-]+", value.casefold(), flags=re.UNICODE)
        if len(token) > 1 and token not in _STOPWORDS
    }


def retrieve_evidence(
    packet: list[ScopedEvidence],
    *,
    route: Literal["structured", "notes", "hybrid", "not_allowed"],
    question: str | None,
    limit: int = 12,
) -> list[ScopedEvidence]:
    """Filter, lexical-rank, deduplicate and cap an already scoped packet."""
    if route == "not_allowed":
        return []
    candidates = [
        scoped
        for scoped in packet
        if scoped.record_status not in {"entered-in-error", "entered-inerror"}
        and (route == "hybrid" or scoped.origin == ("structured" if route == "structured" else "note"))
    ]
    query_terms = _terms(question or "")
    ranked: list[tuple[int, int, ScopedEvidence]] = []
    for index, scoped in enumerate(candidates):
        score = len(query_terms & _terms(_search_text(scoped.item))) if query_terms else 1
        if question and score == 0:
            continue
        if scoped.item.verification_status == "verified":
            score += 1
        ranked.append((score, -index, scoped))
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)

    selected: list[ScopedEvidence] = []
    seen: set[str] = set()
    for _, _, scoped in ranked:
        if scoped.item.evidence_id in seen:
            continue
        seen.add(scoped.item.evidence_id)
        selected.append(scoped)
        if len(selected) >= limit:
            break
    return selected
