"""Backend EvidencePacket for the contract-faithful C3 agent adapter.

The packet is the ONLY interface between Member 1 (data/ingestion) and
Member 2 (agent). Agents never open source files or query the database.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidencePacket(BaseModel):
    """
    The strictly typed backend EvidencePacket.
    Acts as the ONLY interface between data/ingestion and agents.
    """
    model_config = ConfigDict(extra="ignore")

    patient_id: str
    data_watermark: str
    coverage_start: str | None = None
    coverage_end: str | None = None
    encounter_count: int = 0

    timeline: list[dict[str, Any]] = Field(default_factory=list)
    lab_trends: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    latest_observations: list[dict[str, Any]] = Field(default_factory=list)
    active_conditions: list[dict[str, Any]] = Field(default_factory=list)
    current_medications: list[dict[str, Any]] = Field(default_factory=list)
    allergies: list[dict[str, Any]] = Field(default_factory=list)
    fhir_evidence: list[dict[str, Any]] = Field(default_factory=list)

    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    drug_interactions: list[dict[str, Any]] = Field(default_factory=list)
    data_quality_flags: list[dict[str, Any]] = Field(default_factory=list)

    pdf_evidence: list[dict[str, Any]] = Field(default_factory=list)
    pdf_document_ids: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
