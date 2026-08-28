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
        """Prioritize clinical domains based on medical severity (warnings) and diagnosis relevance."""
        from src.clinical.guidelines import parse_and_evaluate_metric, DIAGNOSIS_TO_METRICS
        import datetime

        active_conditions_text = ""
        for c in self.packet:
            ft = c.fact_type.casefold() if c.fact_type else ""
            if "diagnosis" in ft or "condition" in ft:
                src = c.scoped.item.source_value
                active_conditions_text += " " + (" ".join(str(v) for v in src.values()) if isinstance(src, dict) else str(src)).casefold()

        def score_candidate(candidate: RetrievalCandidate) -> float:
            score = 0.0
            fact_type = candidate.fact_type.casefold() if candidate.fact_type else ""
            src = candidate.scoped.item.source_value
            nv = candidate.scoped.item.normalized_value
            src_text = (" ".join(str(v) for v in src.values()) if isinstance(src, dict) else str(src)).casefold()
            
            # Base domain scores
            if "diagnosis" in fact_type or "condition" in fact_type:
                score += 30.0
            elif "medication" in fact_type:
                score += 20.0
            elif "observation" in fact_type or "lab" in fact_type or "vital" in fact_type:
                score += 10.0

            # Evaluate metrics for warnings and diagnosis relevance
            if "observation" in fact_type or "lab" in fact_type or "vital" in fact_type:
                name = ""
                val = None
                unit = ""
                if isinstance(src, dict):
                    name = str(src.get("title", "")).replace("Xét nghiệm:", "").strip()
                    val = str(src.get("summary", "")).replace("Kết quả:", "").strip()
                elif isinstance(nv, dict):
                    name = str(nv.get("statement", "")).split(":")[0] if "statement" in nv else (nv.get("name") or nv.get("code") or "")
                    val = nv.get("statement") or nv.get("value")
                    unit = nv.get("unit", "")
                elif isinstance(nv, str):
                    name = nv.split(":")[0] if ":" in nv else nv
                    val = nv
                
                if name:
                    # Relevance to diagnosis
                    for diag_key, codes in DIAGNOSIS_TO_METRICS.items():
                        if diag_key in active_conditions_text:
                            if any(c in name.casefold() for c in codes) or any(c in src_text for c in codes):
                                score += 40.0
                    
                    # Anomaly check
                    eval_result = parse_and_evaluate_metric(name, val, unit)
                    if eval_result and eval_result.is_warning:
                        score += 50.0

            # Recency boost
            time_str = candidate.scoped.item.source_time
            if time_str:
                try:
                    dt = datetime.datetime.fromisoformat(str(time_str).replace("Z", "+00:00"))
                    now = datetime.datetime.now(dt.tzinfo) if dt.tzinfo else datetime.datetime.now()
                    days_old = (now - dt).days
                    if days_old < 0: days_old = 0
                    score += max(0, 10 - (days_old / 30.0))
                except Exception:
                    pass

            return score

        scored = [(c, score_candidate(c)) for c in self.packet]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Select top items ensuring at least some diversity if possible
        selected = []
        seen_domains = set()
        
        # First pass: try to get the top scored items while capturing top 3 unique domains
        for c, s in scored:
            domain = next((d for d in SUMMARY_DOMAINS if self._matches(c, d)), "other")
            if len(selected) < limit:
                if domain not in seen_domains and len(seen_domains) < 3:
                    selected.append(c)
                    seen_domains.add(domain)
        
        # Second pass: fill the rest with highest scored items not yet selected
        for c, s in scored:
            if len(selected) >= limit:
                break
            if c not in selected:
                selected.append(c)
                
        # Maintain chronological order for readability if they are roughly same score, 
        # but here we just return the highest clinical priority first
        return selected
