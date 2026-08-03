"""Deterministic, evidence-only clinical summary generation for the demo."""

from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from uuid import NAMESPACE_URL, uuid5

from src.clinical.schemas import EvidenceRecord
from src.clinical.summary_schemas import (
    SUMMARY_SECTIONS,
    Citation,
    Claim,
    ClinicalSummaryDraft,
    Conflict,
)
from src.config import get_settings


class SummaryGenerator(ABC):
    @abstractmethod
    def generate(self, evidence: list[EvidenceRecord]) -> ClinicalSummaryDraft:
        """Generate an evidence-backed draft without changing its approval status."""


class DeterministicDemoSummaryGenerator(SummaryGenerator):
    """Formats supplied evidence into a repeatable development/test-only draft."""

    def generate(self, evidence: list[EvidenceRecord]) -> ClinicalSummaryDraft:
        if get_settings().app_env == "production":
            raise RuntimeError("demo summary generator is disabled in production")
        ordered_evidence = sorted(evidence, key=lambda record: record.lineage.source_row_key)
        citation_ids = self._citation_ids(ordered_evidence)
        sections = {section: [] for section in SUMMARY_SECTIONS}
        citations = [self._citation(record, citation_id) for record, citation_id in zip(ordered_evidence, citation_ids)]

        for record, citation_id in zip(ordered_evidence, citation_ids):
            section = self._section_for(record)
            sections[section].append(
                Claim(
                    claim_id=f"claim:{citation_id}",
                    section=section,
                    text=self._claim_text(record),
                    citation_ids=[citation_id],
                    status="VALID",
                )
            )

        subject_id = ordered_evidence[0].lineage.subject_id if ordered_evidence else 0
        hadm_id = ordered_evidence[0].lineage.hadm_id if ordered_evidence else None
        stay_id = ordered_evidence[0].lineage.stay_id if ordered_evidence else None
        evidence_key = "|".join(record.lineage.source_row_key for record in ordered_evidence) or "empty"
        limitations = ["This draft is generated from supplied evidence only and requires clinician review."]
        if not ordered_evidence:
            limitations.insert(0, "No clinical evidence was available for summary generation.")

        return ClinicalSummaryDraft(
            summary_id=uuid5(NAMESPACE_URL, f"clinical-summary:{evidence_key}"),
            subject_id=subject_id,
            hadm_id=hadm_id,
            stay_id=stay_id,
            status="DRAFT",
            sections=sections,
            citations=citations,
            conflicts=self._medication_conflicts(ordered_evidence),
            warnings=[],
            limitations=limitations,
            trace_id=str(uuid5(NAMESPACE_URL, f"clinical-summary-trace:{evidence_key}")),
        )

    @staticmethod
    def _citation(record: EvidenceRecord, citation_id: str) -> Citation:
        return Citation(
            citation_id=citation_id,
            lineage=record.lineage,
            supported_fields=sorted(record.data),
        )

    @staticmethod
    def _citation_ids(evidence: list[EvidenceRecord]) -> list[str]:
        """Keep normal row-key citations while disambiguating cross-table collisions."""
        source_key_counts = Counter(record.lineage.source_row_key for record in evidence)
        occurrences: defaultdict[str, int] = defaultdict(int)
        citation_ids: list[str] = []
        for record in evidence:
            source_key = record.lineage.source_row_key
            if source_key_counts[source_key] == 1:
                citation_ids.append(source_key)
                continue
            occurrences[f"{record.lineage.table}:{source_key}"] += 1
            citation_ids.append(
                f"{record.lineage.table}:{source_key}:{occurrences[f'{record.lineage.table}:{source_key}']}"
            )
        return citation_ids

    @staticmethod
    def _section_for(record: EvidenceRecord) -> str:
        if record.lineage.table == "labevents" or record.record_type == "lab":
            return "Laboratory Trends"
        if record.record_type in {"diagnosis", "procedure"}:
            return "Active Problems"
        if record.record_type == "medication":
            return "Current and Recent Medications"
        if record.record_type in {"admission", "patient"}:
            return "Clinical Overview"
        return "Key Timeline"

    @staticmethod
    def _claim_text(record: EvidenceRecord) -> str:
        lineage = record.lineage
        timestamp = lineage.event_time.isoformat() if lineage.event_time else "timestamp unavailable"
        if record.lineage.table == "labevents" or record.record_type == "lab":
            label = record.data.get("label", record.data.get("itemid", "Laboratory result"))
            value = record.data.get("value", record.data.get("valuenum", "value unavailable"))
            unit = record.data.get("valueuom", "unit unavailable")
            return f"{label}: {value} {unit} at {timestamp}."
        details = ", ".join(f"{key}={value}" for key, value in sorted(record.data.items()))
        return f"{record.record_type.replace('_', ' ').capitalize()}: {details} at {timestamp}."

    @staticmethod
    def _medication_conflicts(evidence: list[EvidenceRecord]) -> list[Conflict]:
        medication_records: dict[str, list[EvidenceRecord]] = defaultdict(list)
        for record in evidence:
            if record.record_type == "medication" and record.data.get("medication"):
                medication_records[str(record.data["medication"]).casefold()].append(record)

        conflicts = []
        for medication, records in sorted(medication_records.items()):
            doses = {str(record.data.get("dose", "")) for record in records}
            if len(doses) > 1:
                conflicts.append(
                    Conflict(
                        conflict_id=f"medication-conflict:{medication}",
                        topic=f"Conflicting medication information for {medication}",
                        evidence_ids=[record.lineage.source_row_key for record in records],
                        status="UNRESOLVED",
                        resolution_note=None,
                    )
                )
        return conflicts
