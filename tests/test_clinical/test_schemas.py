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


def test_query_requires_positive_subject_and_bounded_limit():
    with pytest.raises(ValidationError):
        ClinicalQuery(subject_id=0)
    with pytest.raises(ValidationError):
        ClinicalQuery(subject_id=1, limit=1001)


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
        trace_id="trace-1",
    )

    assert response.records[0].data["value"] == "1.2"
    assert response.warnings == []
    assert context.assigned_subject_ids == {1}


def test_domain_errors_are_concrete_exceptions():
    for error_type in (
        ClinicalAuthNotConfigured,
        ClinicalAccessDenied,
        ClinicalScopeInvalid,
        ClinicalDatabaseUnavailable,
        ClinicalQueryTimeout,
    ):
        assert issubclass(error_type, Exception)
