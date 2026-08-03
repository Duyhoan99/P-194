"""Validation of clinical summary claims against their supplied evidence."""

import re

from src.clinical.availability import ALLOWED_SOURCE_TABLES
from src.clinical.schemas import EvidenceRecord
from src.clinical.summary_schemas import (
    Citation,
    Claim,
    ClinicalSummaryDraft,
    ValidationIssue,
    ValidationReport,
)

_NUMERIC_WITH_UNIT_PATTERN = r"(-?\d+(?:\.\d+)?)\s+{unit}"


class ClaimValidator:
    """Rejects claims whose citations cannot substantiate the supplied text."""

    def validate(
        self, draft: ClinicalSummaryDraft, evidence: list[EvidenceRecord]
    ) -> ValidationReport:
        evidence_by_id = {record.lineage.source_row_key: record for record in evidence}
        citations_by_id = {citation.citation_id: citation for citation in draft.citations}
        errors: list[ValidationIssue] = []

        for claims in draft.sections.values():
            for claim in claims:
                errors.extend(self._validate_claim(claim, citations_by_id, evidence_by_id))
        return ValidationReport(valid=not errors, errors=errors, warnings=[])

    def _validate_claim(
        self,
        claim: Claim,
        citations_by_id: dict[str, Citation],
        evidence_by_id: dict[str, EvidenceRecord],
    ) -> list[ValidationIssue]:
        if not claim.citation_ids:
            return [self._issue("MISSING_CITATION", claim.claim_id, "Claim has no citation IDs.")]

        errors = []
        for citation_id in claim.citation_ids:
            evidence_record = evidence_by_id.get(citation_id)
            citation = citations_by_id.get(citation_id)
            if evidence_record is None:
                errors.append(self._issue("MISSING_SOURCE", claim.claim_id, "Cited evidence is unavailable."))
                continue
            if citation is None:
                errors.append(self._issue("MISSING_CITATION", claim.claim_id, "Citation is unavailable."))
                continue
            if evidence_record.lineage.table not in ALLOWED_SOURCE_TABLES:
                errors.append(self._issue("UNAVAILABLE_SOURCE", claim.claim_id, "Source table is unavailable."))
                continue
            if citation.lineage != evidence_record.lineage:
                errors.append(self._issue("LINEAGE_MISMATCH", claim.claim_id, "Citation lineage differs from evidence."))
                continue
            if self._is_lab(evidence_record):
                errors.extend(self._validate_value_and_unit(claim.text, evidence_record, claim.claim_id))
            else:
                errors.extend(
                    self._validate_supported_fields(claim.text, citation, evidence_record, claim.claim_id)
                )
            errors.extend(self._validate_timestamp(claim.text, evidence_record, claim.claim_id))
        return errors

    @staticmethod
    def _validate_value_and_unit(text: str, evidence: EvidenceRecord, claim_id: str) -> list[ValidationIssue]:
        value = evidence.data.get("valuenum", evidence.data.get("value"))
        unit = evidence.data.get("valueuom")
        if value is None or unit is None:
            return []
        try:
            expected_value = float(value)
        except (TypeError, ValueError):
            return []

        unit_matches = _NUMERIC_WITH_UNIT_PATTERN.format(unit=re.escape(str(unit)))
        claim_values = {float(match) for match in re.findall(unit_matches, text)}
        if expected_value not in claim_values:
            return [
                ClaimValidator._issue(
                    "NUMERIC_VALUE_MISMATCH", claim_id, "Claim numeric value differs from cited evidence."
                )
            ]
        if str(unit) not in text:
            return [
                ClaimValidator._issue(
                    "UNIT_MISMATCH", claim_id, "Claim unit differs from cited evidence."
                )
            ]
        return []

    @staticmethod
    def _is_lab(evidence: EvidenceRecord) -> bool:
        return evidence.record_type == "lab" or evidence.lineage.table == "labevents"

    @staticmethod
    def _validate_supported_fields(
        text: str, citation: Citation, evidence: EvidenceRecord, claim_id: str
    ) -> list[ValidationIssue]:
        if not citation.supported_fields:
            return [
                ClaimValidator._issue(
                    "UNSUPPORTED_CLAIM", claim_id, "Non-laboratory claim has no supported evidence fields."
                )
            ]
        for field_name in citation.supported_fields:
            if field_name not in evidence.data:
                return [
                    ClaimValidator._issue(
                        "UNSUPPORTED_FIELD", claim_id, "Citation references an unavailable evidence field."
                    )
                ]
            if f"{field_name}={evidence.data[field_name]}" not in text:
                return [
                    ClaimValidator._issue(
                        "UNSUPPORTED_CLAIM", claim_id, "Claim text omits cited evidence values."
                    )
                ]
        return []

    @staticmethod
    def _validate_timestamp(text: str, evidence: EvidenceRecord, claim_id: str) -> list[ValidationIssue]:
        timestamp = evidence.lineage.event_time
        expected_timestamp = timestamp.isoformat() if timestamp else "timestamp unavailable"
        if expected_timestamp not in text:
            return [
                ClaimValidator._issue(
                    "TIMESTAMP_MISMATCH", claim_id, "Claim timestamp differs from cited evidence."
                )
            ]
        return []

    @staticmethod
    def _issue(code: str, claim_id: str, message: str) -> ValidationIssue:
        return ValidationIssue(code=code, claim_id=claim_id, message=message)
