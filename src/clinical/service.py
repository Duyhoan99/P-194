"""Access-controlled orchestration for clinical repository retrievals."""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

from src.clinical.access import AssignmentChecker
from src.clinical.audit import AuditAction, AuditEvent, AuditResult, AuditSink
from src.clinical.errors import (
    ClinicalAccessDenied,
    ClinicalDatabaseUnavailable,
    ClinicalQueryTimeout,
    ClinicalScopeInvalid,
)
from src.clinical.repository import ClinicalRepository, RepositoryFetch
from src.clinical.schemas import AccessContext, ClinicalQuery, ClinicalResponse


class ClinicalRetrievalService:
    """Coordinates access, scope validation, retrieval status, and audit events."""

    def __init__(
        self,
        repository: ClinicalRepository,
        access_checker: AssignmentChecker,
        audit_sink: AuditSink,
    ) -> None:
        self._repository = repository
        self._access_checker = access_checker
        self._audit_sink = audit_sink

    def get_patient_overview(self, context: AccessContext, query: ClinicalQuery) -> ClinicalResponse:
        return self._retrieve(
            context, query, "VIEW_PATIENT_OVERVIEW", self._repository.fetch_patient_overview
        )

    def get_encounter_timeline(self, context: AccessContext, query: ClinicalQuery) -> ClinicalResponse:
        return self._retrieve(
            context, query, "VIEW_ENCOUNTER_TIMELINE", self._repository.fetch_encounter_timeline
        )

    def get_diagnoses_and_procedures(self, context: AccessContext, query: ClinicalQuery) -> ClinicalResponse:
        return self._retrieve(
            context,
            query,
            "VIEW_DIAGNOSES_AND_PROCEDURES",
            self._repository.fetch_diagnoses_and_procedures,
        )

    def get_laboratory_results(self, context: AccessContext, query: ClinicalQuery) -> ClinicalResponse:
        return self._retrieve(
            context, query, "VIEW_LABORATORY_RESULTS", self._repository.fetch_laboratory_results
        )

    def get_microbiology_results(self, context: AccessContext, query: ClinicalQuery) -> ClinicalResponse:
        return self._retrieve(
            context, query, "VIEW_MICROBIOLOGY_RESULTS", self._repository.fetch_microbiology_results
        )

    def get_icu_events(self, context: AccessContext, query: ClinicalQuery) -> ClinicalResponse:
        return self._retrieve(context, query, "VIEW_ICU_EVENTS", self._repository.fetch_icu_events)

    def _retrieve(
        self,
        context: AccessContext,
        query: ClinicalQuery,
        action: AuditAction,
        fetch: Callable[[ClinicalQuery], RepositoryFetch],
    ) -> ClinicalResponse:
        try:
            self._access_checker.assert_access(context, query.subject_id)
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
            result = fetch(query)
        except ClinicalScopeInvalid:
            self._record_audit(context, query, action, "ERROR")
            raise
        except ClinicalQueryTimeout:
            self._record_audit(context, query, action, "ERROR")
            raise
        except TimeoutError:
            self._record_audit(context, query, action, "ERROR")
            raise ClinicalQueryTimeout from None
        except sqlite3.OperationalError:
            self._record_audit(context, query, action, "ERROR")
            raise ClinicalDatabaseUnavailable from None

        response = self._response_for_fetch(result, context.trace_id)
        self._record_audit(context, query, action, response.status)
        return response

    @staticmethod
    def _response_for_fetch(result: RepositoryFetch, trace_id: str) -> ClinicalResponse:
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
        return ClinicalResponse(
            status=status,
            records=result.records,
            warnings=warnings,
            limitations=limitations,
            trace_id=trace_id,
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
