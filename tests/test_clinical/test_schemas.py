from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.clinical.errors import (
    ClinicalAccessDenied,
    ClinicalAuthNotConfigured,
    ClinicalDatabaseUnavailable,
    ClinicalQueryTimeout,
    ClinicalScopeInvalid,
)
from src.clinical.schemas import (
    AccessContext,
    ClinicalQuery,
    ClinicalResponse,
    EvidenceRecord,
    SourceLineage,
)
from src.config import Settings


def test_query_requires_positive_subject_and_bounded_limit():
    with pytest.raises(ValidationError):
        ClinicalQuery(subject_id=0)
    with pytest.raises(ValidationError):
        ClinicalQuery(subject_id=1, limit=1001)
    with pytest.raises(ValidationError):
        ClinicalQuery(subject_id=1, cursor="x" * 10001)


def test_query_rejects_non_positive_encounter_ids():
    with pytest.raises(ValidationError):
        ClinicalQuery(subject_id=1, hadm_id=0)
    with pytest.raises(ValidationError):
        ClinicalQuery(subject_id=1, stay_id=-1)


def test_query_rejects_reversed_time_window():
    with pytest.raises(ValidationError):
        ClinicalQuery(
            subject_id=1,
            from_time=datetime(2025, 1, 2, tzinfo=UTC),
            to_time=datetime(2025, 1, 1, tzinfo=UTC),
        )


def test_query_rejects_mixed_timezone_awareness():
    with pytest.raises(ValidationError):
        ClinicalQuery(
            subject_id=1,
            from_time=datetime(2025, 1, 1),
            to_time=datetime(2025, 1, 2, tzinfo=UTC),
        )


def test_query_rejects_any_naive_datetime():
    with pytest.raises(ValidationError):
        ClinicalQuery(subject_id=1, from_time=datetime(2025, 1, 1))
    with pytest.raises(ValidationError):
        ClinicalQuery(subject_id=1, to_time=datetime(2025, 1, 2))


def test_production_settings_require_postgres_and_cursor_secret():
    with pytest.raises(ValueError):
        Settings(app_env="production", clinical_backend="sqlite", clinical_cursor_secret="secret")
    with pytest.raises(ValueError):
        Settings(app_env="production", clinical_backend="postgresql", clinical_postgres_dsn="")


def test_lineage_requires_mimic_version_and_source_identity():
    lineage = SourceLineage(
        dataset="MIMIC-IV",
        version="3.1",
        module="hosp",
        table="labevents",
        source_row_key="labevent_id=1",
        subject_id=1,
        event_time=None,
    )
    assert lineage.table == "labevents"


def test_lineage_supports_an_explicit_non_mimic_source_profile():
    lineage = SourceLineage(
        dataset="hospital-ehr",
        version="2026-01",
        module="hosp",
        table="labevents",
        source_row_key="lab-result=1",
        subject_id=1,
        event_time=None,
    )

    assert lineage.dataset == "hospital-ehr"


def test_contract_models_preserve_defaults_and_context():
    lineage = SourceLineage(
        dataset="MIMIC-IV",
        version="3.1",
        module="icu",
        table="chartevents",
        source_row_key="chartevent_id=1",
        subject_id=1,
        event_time=None,
    )
    record = EvidenceRecord(record_type="lab", data={"value": "1.2"}, lineage=lineage)
    response = ClinicalResponse(
        status="SUCCESS",
        records=[record],
        warnings=[],
        limitations=[],
        trace_id="trace-1",
    )
    context = AccessContext(
        user_id="doctor-1",
        role="DOCTOR",
        assigned_subject_ids={1},
        trace_id="123e4567-e89b-42d3-a456-426614174000",
    )

    assert response.records[0].data["value"] == "1.2"
    assert response.warnings == []
    assert response.page.next_cursor is None
    assert response.page.has_more is False
    assert context.assigned_subject_ids == {1}


def test_access_context_rejects_noncanonical_v4_trace_id():
    """Removing the trace ID contract would defer denial failure to audit recording."""
    with pytest.raises(ValidationError):
        AccessContext(
            user_id="doctor-1",
            role="DOCTOR",
            assigned_subject_ids={1},
            trace_id="not-a-uuid",
        )


def test_domain_errors_are_concrete_exceptions():
    for error_type in (
        ClinicalAuthNotConfigured,
        ClinicalAccessDenied,
        ClinicalScopeInvalid,
        ClinicalDatabaseUnavailable,
        ClinicalQueryTimeout,
    ):
        assert issubclass(error_type, Exception)
