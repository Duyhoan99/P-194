"""Access-aware orchestration for evidence-first clinical summary generation."""

from datetime import UTC, datetime

from src.clinical.audit import AuditEvent, AuditResult, AuditSink
from src.clinical.claim_validator import ClaimValidator
from src.clinical.errors import ClinicalAccessDenied, ReviewPolicyError
from src.clinical.schemas import AccessContext, ClinicalQuery, ClinicalResponse, EvidenceRecord
from src.clinical.service import ClinicalRetrievalService
from src.clinical.summary_generator import DeterministicDemoSummaryGenerator, SummaryGenerator
from src.clinical.summary_schemas import ClinicalSummaryDraft


class ClinicalSummaryService:
    """Retrieves only authorized evidence before creating a draft summary."""

    def __init__(
        self,
        retrieval_service: ClinicalRetrievalService,
        generator: SummaryGenerator | None = None,
        *,
        audit_sink: AuditSink,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._generator = generator or DeterministicDemoSummaryGenerator()
        self._audit_sink = audit_sink

    def generate(self, context: AccessContext, query: ClinicalQuery) -> ClinicalSummaryDraft:
        try:
            responses = self._responses(context, query)
            if any(response.status == "DENIED" for response in responses):
                raise ClinicalAccessDenied
            evidence = [record for response in responses for record in response.records]
            draft = self._generator.generate(evidence)
        except ClinicalAccessDenied:
            self._record_audit(context, query, "DENIED")
            raise
        except Exception:
            self._record_audit(context, query, "ERROR")
            raise

        result = self._result_for(responses, evidence)
        self._record_audit(context, query, result)
        return draft.model_copy(
            update={
                "subject_id": query.subject_id,
                "hadm_id": query.hadm_id,
                "stay_id": query.stay_id,
                "trace_id": context.trace_id,
                "warnings": self._unique(response.warnings for response in responses),
                "limitations": [
                    *draft.limitations,
                    *self._unique(response.limitations for response in responses),
                ],
            }
        )

    def validate_edit(
        self,
        context: AccessContext,
        original: ClinicalSummaryDraft,
        patch: ClinicalSummaryDraft,
    ) -> None:
        """Re-fetch original-scope evidence before allowing an edited version."""
        if (patch.subject_id, patch.hadm_id, patch.stay_id) != (
            original.subject_id,
            original.hadm_id,
            original.stay_id,
        ):
            raise ReviewPolicyError("Edited summary scope must remain unchanged.")
        query = ClinicalQuery(
            subject_id=original.subject_id,
            hadm_id=original.hadm_id,
            stay_id=original.stay_id,
        )
        responses = self._responses(context, query)
        if any(response.status == "DENIED" for response in responses):
            raise ClinicalAccessDenied
        evidence = [record for response in responses for record in response.records]
        report = ClaimValidator().validate(patch, evidence)
        if not report.valid:
            raise ReviewPolicyError("Edited claims require evidence-backed citations.")

    def _responses(self, context: AccessContext, query: ClinicalQuery) -> tuple[ClinicalResponse, ...]:
        return (
            self._retrieval_service.get_patient_overview(context, query),
            self._retrieval_service.get_encounter_timeline(context, query),
            self._retrieval_service.get_diagnoses_and_procedures(context, query),
            self._retrieval_service.get_laboratory_results(context, query),
            self._retrieval_service.get_microbiology_results(context, query),
            self._retrieval_service.get_icu_events(context, query),
        )

    @staticmethod
    def _unique(groups) -> list[str]:
        return list(dict.fromkeys(item for group in groups for item in group))

    @staticmethod
    def _result_for(responses: tuple[ClinicalResponse, ...], evidence: list[EvidenceRecord]) -> AuditResult:
        if any(response.status in {"PARTIAL", "NOT_LOADED"} for response in responses):
            return "PARTIAL" if evidence else "NOT_LOADED"
        return "SUCCESS" if evidence else "EMPTY"

    def _record_audit(self, context: AccessContext, query: ClinicalQuery, result: AuditResult) -> None:
        self._audit_sink.record(
            AuditEvent(
                user_id=context.user_id,
                action="GENERATE_CLINICAL_SUMMARY",
                subject_id=query.subject_id,
                hadm_id=query.hadm_id,
                stay_id=query.stay_id,
                result=result,
                trace_id=context.trace_id,
                timestamp=datetime.now(UTC),
            )
        )
