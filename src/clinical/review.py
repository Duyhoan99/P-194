"""Authorization-checked clinician review policy for persisted summaries."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel

from src.clinical.access import AssignmentChecker
from src.clinical.audit import AuditEvent, AuditSink
from src.clinical.errors import ClinicalAccessDenied, ClinicalSummaryNotFound, ReviewPolicyError
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
        summary = self._authorized_summary(summary_id, context, "REJECT_CLINICAL_SUMMARY")
        if not reason.strip():
            self._audit(summary, context, "REJECT_CLINICAL_SUMMARY", "ERROR")
            raise ReviewPolicyError("A rejection reason is required.")
        return self._transition(summary, context, "REJECTED", reason, "REJECT_CLINICAL_SUMMARY")

    def get(self, summary_id: UUID, context: AccessContext) -> SummaryVersion:
        """Return a summary only after the established assigned-doctor policy."""
        return self._authorized_summary(summary_id, context, "EDIT_CLINICAL_SUMMARY")

    def list_versions(self, summary_id: UUID, context: AccessContext) -> list[SummaryVersion]:
        """Return immutable version metadata only for an authorized doctor."""
        summary = self._authorized_summary(summary_id, context, "EDIT_CLINICAL_SUMMARY")
        return self._repository.list_versions(summary.summary_id)

    def edit(
        self,
        summary_id: UUID,
        context: AccessContext,
        patch: ClinicalSummaryDraft,
        reason: str | None,
    ) -> SummaryVersion:
        summary = self._authorized_summary(summary_id, context, "EDIT_CLINICAL_SUMMARY")
        if not self._has_valid_citations_for_draft(patch):
            self._audit(summary, context, "EDIT_CLINICAL_SUMMARY", "ERROR")
            raise ReviewPolicyError("Edited claims require valid citations.")
        try:
            version = self._repository.update_draft(summary.summary_id, context.user_id, patch, reason)
        except Exception:
            self._audit(summary, context, "EDIT_CLINICAL_SUMMARY", "ERROR")
            raise
        self._audit(version, context, "EDIT_CLINICAL_SUMMARY", "SUCCESS", persist=False)
        return version

    def approve(self, summary_id: UUID, context: AccessContext, checklist: ReviewChecklist) -> SummaryVersion:
        summary = self._authorized_summary(summary_id, context, "APPROVE_CLINICAL_SUMMARY")
        if not checklist.is_complete() or not self._has_valid_citations(summary) or not self._has_confirmed_conflicts(summary):
            self._audit(summary, context, "APPROVE_CLINICAL_SUMMARY", "ERROR")
            raise ReviewPolicyError("Approval requires completed review and valid citations.")
        event = self._event(summary, context, "APPROVE_CLINICAL_SUMMARY", "SUCCESS")
        try:
            version = self._repository.approve(
                summary.summary_id, context.user_id, tuple(checklist.model_dump().values()), event
            )
        except Exception:
            self._audit(summary, context, "APPROVE_CLINICAL_SUMMARY", "ERROR")
            raise
        if self._audit_sink is not self._repository:
            self._audit_sink.record(event)
        return version

    def export(self, summary_id: UUID, context: AccessContext) -> SummaryVersion:
        summary = self._authorized_summary(summary_id, context, "EXPORT_CLINICAL_SUMMARY")
        if summary.status != "APPROVED":
            self._audit(summary, context, "EXPORT_CLINICAL_SUMMARY", "ERROR")
            raise ReviewPolicyError("Only approved summaries may be exported.")
        return self._transition(summary, context, "EXPORTED", None, "EXPORT_CLINICAL_SUMMARY")

    def confirm_conflict(
        self, summary_id: UUID, context: AccessContext, conflict_id: str, resolution_note: str
    ) -> SummaryVersion:
        summary = self._authorized_summary(summary_id, context, "RESOLVE_CLINICAL_CONFLICT")
        if not resolution_note.strip():
            self._audit(summary, context, "RESOLVE_CLINICAL_CONFLICT", "ERROR")
            raise ReviewPolicyError("A conflict resolution note is required.")
        event = self._event(summary, context, "RESOLVE_CLINICAL_CONFLICT", "SUCCESS")
        try:
            version = self._repository.confirm_conflict(
                summary.summary_id, context.user_id, conflict_id, resolution_note, event
            )
        except Exception:
            self._audit(summary, context, "RESOLVE_CLINICAL_CONFLICT", "ERROR")
            raise
        if self._audit_sink is not self._repository:
            self._audit_sink.record(event)
        return version

    def _authorized_summary(self, summary_id: UUID, context: AccessContext, action: str) -> SummaryVersion:
        if context.role != "DOCTOR":
            self._audit_denied(context, action, None)
            raise ClinicalAccessDenied
        for subject_id in context.assigned_subject_ids:
            try:
                self._assignments.assert_access(context, subject_id)
            except ClinicalAccessDenied:
                self._audit_denied(context, action, subject_id)
                raise
            summary = self._repository.get_for_subject(summary_id, subject_id)
            if summary is not None:
                return summary
        try:
            self._repository.get(summary_id)
        except ReviewPolicyError:
            raise ClinicalSummaryNotFound from None
        self._audit_denied(context, action, None)
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
        return ReviewService._has_valid_citations_for_draft(summary.draft)

    @staticmethod
    def _has_valid_citations_for_draft(draft: ClinicalSummaryDraft) -> bool:
        citations = {citation.citation_id for citation in draft.citations}
        return all(
            claim.status == "VALID" and bool(claim.citation_ids) and set(claim.citation_ids) <= citations
            for claims in draft.sections.values()
            for claim in claims
        )

    def _has_confirmed_conflicts(self, summary: SummaryVersion) -> bool:
        confirmations = self._repository.confirmed_conflicts(summary.version_id)
        return all(
            conflict.status == "UNRESOLVED"
            or (conflict.resolved_by is not None and conflict.resolution_note is not None)
            and (conflict.conflict_id, conflict.resolved_by, conflict.resolution_note) in confirmations
            for conflict in summary.draft.conflicts
        )

    def _audit(
        self, summary: SummaryVersion, context: AccessContext, action: str, result: str, *, persist: bool = True
    ) -> None:
        event = self._event(summary, context, action, result)
        if persist:
            self._repository.record(event)
        if self._audit_sink is not self._repository:
            self._audit_sink.record(event)

    @staticmethod
    def _event(summary: SummaryVersion, context: AccessContext, action: str, result: str) -> AuditEvent:
        return AuditEvent(
            user_id=context.user_id, action=action, subject_id=summary.draft.subject_id,
            hadm_id=summary.draft.hadm_id, stay_id=summary.draft.stay_id, result=result,
            trace_id=context.trace_id, timestamp=datetime.now(UTC),
        )

    def _audit_denied(self, context: AccessContext, action: str, subject_id: int | None) -> None:
        event = AuditEvent(
            user_id=context.user_id, action=action, subject_id=subject_id or 0, hadm_id=None, stay_id=None,
            result="DENIED", trace_id=context.trace_id, timestamp=datetime.now(UTC),
        )
        self._repository.record(event)
        if self._audit_sink is not self._repository:
            self._audit_sink.record(event)
