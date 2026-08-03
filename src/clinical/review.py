"""Authorization-checked clinician review policy for persisted summaries."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel

from src.clinical.access import AssignmentChecker
from src.clinical.audit import AuditEvent, AuditSink
from src.clinical.errors import ClinicalAccessDenied, ReviewPolicyError
from src.clinical.schemas import AccessContext
from src.clinical.summary_repository import SQLiteSummaryRepository, SummaryVersion
from src.clinical.summary_schemas import ClinicalSummaryDraft


class ReviewChecklist(BaseModel):
    reviewed_summary: bool
    checked_critical_evidence: bool
    understands_ai_limitations: bool
    confirms_edits: bool

    def is_complete(self) -> bool:
        return all(self.model_dump().values())


class ReviewService:
    def __init__(
        self, repository: SQLiteSummaryRepository, assignments: AssignmentChecker, audit_sink: AuditSink
    ) -> None:
        self._repository = repository
        self._assignments = assignments
        self._audit_sink = audit_sink

    def reject(self, summary_id: UUID, context: AccessContext, reason: str) -> SummaryVersion:
        summary = self._authorized_summary(summary_id, context)
        if not reason.strip():
            self._audit(summary, context, "REJECT_CLINICAL_SUMMARY", "ERROR")
            raise ReviewPolicyError("A rejection reason is required.")
        return self._transition(summary, context, "REJECTED", reason, "REJECT_CLINICAL_SUMMARY")

    def edit(
        self,
        summary_id: UUID,
        context: AccessContext,
        patch: ClinicalSummaryDraft,
        reason: str | None,
    ) -> SummaryVersion:
        summary = self._authorized_summary(summary_id, context)
        try:
            version = self._repository.update_draft(summary.summary_id, context.user_id, patch, reason)
        except Exception:
            self._audit(summary, context, "EDIT_CLINICAL_SUMMARY", "ERROR")
            raise
        self._audit(version, context, "EDIT_CLINICAL_SUMMARY", "SUCCESS", persist=False)
        return version

    def approve(self, summary_id: UUID, context: AccessContext, checklist: ReviewChecklist) -> SummaryVersion:
        summary = self._authorized_summary(summary_id, context)
        if not checklist.is_complete() or not self._has_valid_citations(summary):
            self._audit(summary, context, "APPROVE_CLINICAL_SUMMARY", "ERROR")
            raise ReviewPolicyError("Approval requires completed review and valid citations.")
        version = self._transition(summary, context, "APPROVED", None, "APPROVE_CLINICAL_SUMMARY")
        self._repository.save_checklist(version.version_id, tuple(checklist.model_dump().values()))
        return version

    def export(self, summary_id: UUID, context: AccessContext) -> SummaryVersion:
        summary = self._authorized_summary(summary_id, context)
        if summary.status != "APPROVED":
            self._audit(summary, context, "EXPORT_CLINICAL_SUMMARY", "ERROR")
            raise ReviewPolicyError("Only approved summaries may be exported.")
        return self._transition(summary, context, "EXPORTED", None, "EXPORT_CLINICAL_SUMMARY")

    def _authorized_summary(self, summary_id: UUID, context: AccessContext) -> SummaryVersion:
        if context.role != "DOCTOR":
            raise ClinicalAccessDenied
        for subject_id in context.assigned_subject_ids:
            self._assignments.assert_access(context, subject_id)
            summary = self._repository.get_for_subject(summary_id, subject_id)
            if summary is not None:
                return summary
        raise ClinicalAccessDenied

    def _transition(
        self, summary: SummaryVersion, context: AccessContext, status: str, reason: str | None, action: str
    ) -> SummaryVersion:
        try:
            version = self._repository.transition(summary.summary_id, status, context.user_id, reason)
        except Exception:
            self._audit(summary, context, action, "ERROR")
            raise
        self._audit(version, context, action, "SUCCESS")
        return version

    @staticmethod
    def _has_valid_citations(summary: SummaryVersion) -> bool:
        citations = {citation.citation_id for citation in summary.draft.citations}
        return all(
            claim.status == "VALID" and bool(claim.citation_ids) and set(claim.citation_ids) <= citations
            for claims in summary.draft.sections.values()
            for claim in claims
        )

    def _audit(
        self, summary: SummaryVersion, context: AccessContext, action: str, result: str, *, persist: bool = True
    ) -> None:
        event = AuditEvent(
            user_id=context.user_id, action=action, subject_id=summary.draft.subject_id,
            hadm_id=summary.draft.hadm_id, stay_id=summary.draft.stay_id, result=result,
            trace_id=context.trace_id, timestamp=datetime.now(UTC),
        )
        if persist:
            self._repository.record(event)
        if self._audit_sink is not self._repository:
            self._audit_sink.record(event)
