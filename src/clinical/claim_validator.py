"""Validation of clinical summary claims against their supplied evidence."""

import re

from src.clinical.availability import ALLOWED_SOURCE_TABLES
from src.clinical.schemas import EvidenceRecord
from src.clinical.summary_schemas import ClinicalSummaryDraft, ValidationIssue, ValidationReport

_DECIMAL_PATTERN = re.compile(r"(?<![\w.])-?\d+\.\d+(?![\w.])")


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

    def _validate_claim(self, claim, citations_by_id, evidence_by_id) -> list[ValidationIssue]:
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
            errors.extend(self._validate_value_and_unit(claim.text, evidence_record, claim.claim_id))
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

        claim_values = {float(match) for match in _DECIMAL_PATTERN.findall(text)}
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
    def _issue(code: str, claim_id: str, message: str) -> ValidationIssue:
        return ValidationIssue(code=code, claim_id=claim_id, message=message)
