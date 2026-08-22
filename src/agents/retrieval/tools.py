"""Typed, patient-scoped retrieval tools over an already validated packet."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import re
from src.agents.retrieval.concepts import fold as _fold, get_concept

if TYPE_CHECKING:
    from src.agents.evidence import ScopedEvidence


SUMMARY_DOMAINS = (
    "diagnosis",
    "medication",
    "lab",
    "vital",
    "encounter",
    "note",
    "procedure",
    "symptom",
)

def _candidate_text(candidate: "RetrievalCandidate") -> str:
    item = candidate.scoped.item
    snippets = " ".join(citation.snippet for citation in item.citations)
    return _fold(f"{item.fact_type} {item.normalized_value} {item.source_value} {snippets}")


from src.agents.retrieval.concepts import fold as _fold, get_concept, resolve_concept

def _entity_aliases(entity: str) -> tuple[str, ...]:
    concept = get_concept(entity) or resolve_concept(entity)
    if concept:
        return concept.evidence_aliases
    folded = _fold(entity)
    tokens = tuple(token for token in re.findall(r"[\w./+-]+", folded) if len(token) > 1)
    return tokens or (folded,)


def _is_known_entity(entity: str) -> bool:
    return (get_concept(entity) or resolve_concept(entity)) is not None


@dataclass
class RetrievalCandidate:
    """A scored view over one item from the locked, validated evidence packet."""

    scoped: ScopedEvidence
    semantic_score: float = 0.0

    @property
    def verification_status(self):
        return self.scoped.item.verification_status

    @property
    def fact_type(self):
        return self.scoped.item.fact_type

    @property
    def normalized_value(self):
        return self.scoped.item.normalized_value

    @property
    def evidence_id(self):
        return self.scoped.item.evidence_id


class SafeTool:
    """Select only preloaded candidates; never opens storage or changes scope."""

    def __init__(
        self,
        *,
        tenant_id: str,
        patient_id: str,
        preloaded_packet: list[RetrievalCandidate] | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.patient_id = patient_id
        self.packet = preloaded_packet or []

    @staticmethod
    def _matches(candidate: RetrievalCandidate, domain: str) -> bool:
        if domain == "all":
            return True
        fact_type = candidate.fact_type.casefold() if candidate.fact_type else ""
        origin = candidate.scoped.origin
        source = candidate.scoped.item.source_value
        source_text = " ".join(str(value) for value in source.values()).casefold() if isinstance(source, dict) else str(source).casefold()
        vital_markers = ("blood pressure", "heart rate", "body weight", "huyết áp", "mạch", "cân nặng")
        if domain == "lab" and "observation" in fact_type and any(marker in source_text for marker in vital_markers):
            return False
        if domain == "vital" and "observation" in fact_type:
            return any(marker in source_text for marker in vital_markers)
        markers = {
            "diagnosis": ("diagnosis", "condition", "chẩn đoán", "bệnh", "tình trạng"),
            "medication": ("medication", "drug", "thuốc", "tuân thủ"),
            "lab": ("lab", "observation", "result", "xét nghiệm", "chỉ số", "canonical_unit_backend_fact"),
            "vital": ("vital", "huyết áp", "mạch"),
            "encounter": ("encounter", "lượt khám", "tái khám"),
            "note": ("note", "ghi chú", "clinical_note", "narrative"),
            "procedure": ("procedure", "thủ thuật"),
            "symptom": ("symptom", "triệu chứng"),
        }
        if domain == "note" and origin == "note":
            return True
        matched_in_fact_type = any(marker in fact_type for marker in markers.get(domain, (domain,)))
        matched_in_source = any(marker in source_text for marker in markers.get(domain, (domain,)))
        return matched_in_fact_type or matched_in_source

    def execute(self, domain: str) -> list[RetrievalCandidate]:
        return [candidate for candidate in self.packet if self._matches(candidate, domain)]

    def filter_entity(
        self, candidates: list[RetrievalCandidate], entity: str
    ) -> list[RetrievalCandidate]:
        """Apply the explicit plan entity after scope/domain filtering."""
        aliases = _entity_aliases(entity)
        return [
            candidate for candidate in candidates
            if (
                any(alias in _candidate_text(candidate) for alias in aliases)
                if _is_known_entity(entity)
                else all(alias in _candidate_text(candidate) for alias in aliases)
            )
        ]

    def execute_summary(self, limit: int) -> list[RetrievalCandidate]:
        """Round-robin clinical domains so a bounded summary is not one-domain-heavy."""
        buckets: dict[str, list[RetrievalCandidate]] = {domain: [] for domain in SUMMARY_DOMAINS}
        unmatched: list[RetrievalCandidate] = []
        for candidate in self.packet:
            matched_domain = next(
                (domain for domain in SUMMARY_DOMAINS if self._matches(candidate, domain)),
                None,
            )
            if matched_domain is None:
                unmatched.append(candidate)
            else:
                buckets[matched_domain].append(candidate)

        selected: list[RetrievalCandidate] = []
        offset = 0
        while len(selected) < limit:
            added = False
            for domain in SUMMARY_DOMAINS:
                bucket = buckets[domain]
                if offset < len(bucket):
                    selected.append(bucket[offset])
                    added = True
                    if len(selected) == limit:
                        return selected
            if not added:
                break
            offset += 1

        for candidate in unmatched:
            if len(selected) == limit:
                break
            selected.append(candidate)
        return selected
