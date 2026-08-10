"""Backend EvidencePacket for the contract-faithful C3 agent adapter.

The packet is the ONLY interface between Member 1 (data/ingestion) and
Member 2 (agent). Agents never open source files or query the database.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidencePacket:
    patient_id: str
    data_watermark: str
    coverage_start: str | None = None
    coverage_end: str | None = None
    encounter_count: int = 0
    timeline: list[dict[str, Any]] = field(default_factory=list)
    lab_trends: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    active_conditions: list[dict[str, Any]] = field(default_factory=list)
    current_medications: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    drug_interactions: list[dict[str, Any]] = field(default_factory=list)
    data_quality_flags: list[dict[str, Any]] = field(default_factory=list)
    # PDF evidence items: list of canonical EvidenceItem dicts with DocumentCitation
    # These are added after successful PDF ingestion and canonicalization.
    pdf_evidence: list[dict[str, Any]] = field(default_factory=list)
    # Track which document_ids have been ingested into this packet
    pdf_document_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "data_watermark": self.data_watermark,
            "coverage_start": self.coverage_start,
            "coverage_end": self.coverage_end,
            "encounter_count": self.encounter_count,
            "timeline": self.timeline,
            "lab_trends": self.lab_trends,
            "active_conditions": self.active_conditions,
            "current_medications": self.current_medications,
            "conflicts": self.conflicts,
            "drug_interactions": self.drug_interactions,
            "data_quality_flags": self.data_quality_flags,
            "pdf_evidence": self.pdf_evidence,
            "pdf_document_ids": self.pdf_document_ids,
        }
