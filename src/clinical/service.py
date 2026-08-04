"""Access-controlled orchestration for clinical repository retrievals."""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from src.clinical.access import AssignmentChecker
from src.clinical.audit import AuditAction, AuditEvent, AuditResult, AuditSink
from src.clinical.errors import (
    ClinicalAccessDenied,
    ClinicalAuthNotConfigured,
    ClinicalDatabaseUnavailable,
    ClinicalQueryTimeout,
    ClinicalScopeInvalid,
)
from src.clinical.pagination import (
    CursorBinding,
    CursorPayload,
    CursorPosition,
    decode_cursor,
    encode_cursor,
)
from src.clinical.repository import ClinicalRepository, RepositoryFetch
from src.clinical.schemas import AccessContext, ClinicalPage, ClinicalQuery, ClinicalResponse
from src.config import get_settings


class ClinicalRetrievalService:
    """Coordinates access, scope validation, retrieval status, and audit events."""

    def __init__(
        self,
        repository: ClinicalRepository,
        access_checker: AssignmentChecker,
        audit_sink: AuditSink,
        *,
        cursor_secret: str | None = None,
        source_profile: str | None = None,
        cursor_ttl_seconds: int | None = None,
    ) -> None:
        self._repository = repository
        self._access_checker = access_checker
        self._audit_sink = audit_sink
        settings = get_settings()
        self._cursor_secret = cursor_secret if cursor_secret is not None else settings.clinical_cursor_secret
        self._source_profile = source_profile or settings.clinical_source_profile
        self._source_dataset = settings.clinical_source_dataset
        self._source_version = settings.clinical_source_version
        self._cursor_ttl_seconds = cursor_ttl_seconds or settings.clinical_cursor_ttl_seconds

    def get_patient_overview(self, context: AccessContext, query: ClinicalQuery) -> ClinicalResponse:
        return self._retrieve(
            context, query, "VIEW_PATIENT_OVERVIEW", "patient_overview", self._repository.fetch_patient_overview
        )

    def get_encounter_timeline(self, context: AccessContext, query: ClinicalQuery) -> ClinicalResponse:
        return self._retrieve(
            context, query, "VIEW_ENCOUNTER_TIMELINE", "encounter_timeline", self._repository.fetch_encounter_timeline
        )

    def get_diagnoses_and_procedures(self, context: AccessContext, query: ClinicalQuery) -> ClinicalResponse:
        return self._retrieve(
            context,
            query,
            "VIEW_DIAGNOSES_AND_PROCEDURES",
            "diagnoses_and_procedures",
            self._repository.fetch_diagnoses_and_procedures,
        )

    def get_laboratory_results(self, context: AccessContext, query: ClinicalQuery) -> ClinicalResponse:
        return self._retrieve(
            context, query, "VIEW_LABORATORY_RESULTS", "laboratory_results", self._repository.fetch_laboratory_results
        )

    def get_microbiology_results(self, context: AccessContext, query: ClinicalQuery) -> ClinicalResponse:
        return self._retrieve(
            context, query, "VIEW_MICROBIOLOGY_RESULTS", "microbiology_results", self._repository.fetch_microbiology_results
        )

    def get_medications(self, context: AccessContext, query: ClinicalQuery) -> ClinicalResponse:
        return self._retrieve(context, query, "VIEW_MEDICATIONS", "medications", self._repository.fetch_medications)

    def get_patient_metrics(self, context: AccessContext, query: ClinicalQuery) -> ClinicalResponse:
        return self._retrieve(context, query, "VIEW_PATIENT_METRICS", "patient_metrics", self._repository.fetch_patient_metrics)

    def get_icu_events(self, context: AccessContext, query: ClinicalQuery) -> ClinicalResponse:
        return self._retrieve(context, query, "VIEW_ICU_EVENTS", "icu_events", self._repository.fetch_icu_events)

    def _retrieve(
        self,
        context: AccessContext,
        query: ClinicalQuery,
        action: AuditAction,
        endpoint: str,
        fetch: Callable[[ClinicalQuery, CursorPosition | None], RepositoryFetch],
    ) -> ClinicalResponse:
        cursor_position = None
        try:
            if query.cursor:
                cursor_position = decode_cursor(
                    query.cursor,
                    self._cursor_secret,
                    self._cursor_binding(query, endpoint),
                ).position
        except ClinicalScopeInvalid:
            self._record_audit(context, query, action, "ERROR")
            raise

        try:
            self._access_checker.assert_access(
                context, query.subject_id, query.hadm_id, query.stay_id
            )
        except ClinicalAccessDenied:
            self._record_audit(context, query, action, "DENIED")
            return ClinicalResponse(
                status="DENIED",
                records=[],
                warnings=["Access to the requested clinical subject is denied."],
                limitations=[],
                trace_id=context.trace_id,
            )

        try:
            if not self._repository.validate_scope(query):
                raise ClinicalScopeInvalid
            result = fetch(query, cursor_position)
        except ClinicalScopeInvalid:
            self._record_audit(context, query, action, "ERROR")
            raise
        except ClinicalQueryTimeout:
            self._record_audit(context, query, action, "ERROR")
            raise ClinicalQueryTimeout from None
        except TimeoutError:
            self._record_audit(context, query, action, "ERROR")
            raise ClinicalQueryTimeout from None
        except sqlite3.DatabaseError:
            self._record_audit(context, query, action, "ERROR")
            raise ClinicalDatabaseUnavailable from None

        try:
            response = self._response_for_fetch(result, context.trace_id, query, endpoint)
        except ClinicalDatabaseUnavailable:
            self._record_audit(context, query, action, "ERROR")
            raise ClinicalDatabaseUnavailable from None
        self._record_audit(context, query, action, response.status)
        return response

    def _response_for_fetch(
        self,
        result: RepositoryFetch,
        trace_id: str,
        query: ClinicalQuery,
        endpoint: str,
    ) -> ClinicalResponse:
        for record in result.records:
            lineage = record.lineage
            if (
                lineage.dataset != self._source_dataset
                or lineage.version != self._source_version
                or lineage.subject_id != query.subject_id
                or (query.hadm_id is not None and lineage.hadm_id not in (None, query.hadm_id))
                or (query.stay_id is not None and lineage.stay_id not in (None, query.stay_id))
            ):
                raise ClinicalDatabaseUnavailable
        warnings = [f"Clinical source unavailable: {source}" for source in result.unavailable_sources]
        if result.unavailable_sources:
            status = "PARTIAL" if result.records else "NOT_LOADED"
            limitations = ["One or more requested clinical sources are unavailable."]
        elif result.records:
            status = "SUCCESS"
            limitations = []
        else:
            status = "EMPTY"
            limitations = []
        next_cursor = None
        if result.has_more:
            if result.next_position is None or not self._cursor_secret:
                raise ClinicalAuthNotConfigured("Clinical cursor signing is not configured")
            issued_at = datetime.now(UTC)
            next_cursor = encode_cursor(
                CursorPayload(
                    binding=self._cursor_binding(query, endpoint),
                    position=result.next_position,
                    issued_at=issued_at,
                    expires_at=issued_at + timedelta(seconds=self._cursor_ttl_seconds),
                ),
                self._cursor_secret,
                now=issued_at,
            )
        return ClinicalResponse(
            status=status,
            records=result.records,
            warnings=warnings,
            limitations=limitations,
            trace_id=trace_id,
            page=ClinicalPage(next_cursor=next_cursor, has_more=result.has_more),
        )

    def _cursor_binding(self, query: ClinicalQuery, endpoint: str) -> CursorBinding:
        return CursorBinding(
            endpoint=endpoint,
            subject_id=query.subject_id,
            hadm_id=query.hadm_id,
            stay_id=query.stay_id,
            from_time=query.from_time,
            to_time=query.to_time,
            source_profile=self._source_profile,
            order_version="v1",
        )

    def _record_audit(
        self,
        context: AccessContext,
        query: ClinicalQuery,
        action: AuditAction,
        result: AuditResult,
    ) -> None:
        self._audit_sink.record(
            AuditEvent(
                user_id=context.user_id,
                action=action,
                subject_id=query.subject_id,
                hadm_id=query.hadm_id,
                stay_id=query.stay_id,
                result=result,
                trace_id=context.trace_id,
                timestamp=datetime.now(UTC),
            )
        )
