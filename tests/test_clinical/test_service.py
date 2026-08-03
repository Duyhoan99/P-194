import sqlite3
from datetime import UTC, datetime

import pytest

from src.clinical.access import DemoAssignmentProvider
from src.clinical.audit import InMemoryAuditSink
from src.clinical.errors import ClinicalDatabaseUnavailable, ClinicalQueryTimeout, ClinicalScopeInvalid
from src.clinical.pagination import CursorPosition
from src.clinical.repository import RepositoryFetch, SQLiteClinicalRepository
from src.clinical.schemas import AccessContext, ClinicalQuery
from src.clinical.service import ClinicalRetrievalService
from tests.clinical_fixtures import create_mock_clinical_db
from tests.test_clinical.conftest import TEST_TRACE_ID, DenyAllChecker, allowed_context


def test_service_denies_before_repository_scope_or_fetch(fake_repo, audit_sink):
    """Skipping the access check before scope validation must fail this test."""
    from src.clinical.service import ClinicalRetrievalService

    service = ClinicalRetrievalService(fake_repo, DenyAllChecker(), audit_sink)
    context = AccessContext(
        user_id="doctor-1",
        role="DOCTOR",
        assigned_subject_ids=set(),
        trace_id=TEST_TRACE_ID,
    )

    result = service.get_laboratory_results(context, ClinicalQuery(subject_id=101))

    assert result.status == "DENIED"
    assert result.records == []
    assert result.trace_id == TEST_TRACE_ID
    assert fake_repo.scope_calls == 0
    assert fake_repo.fetch_calls == []
    assert audit_sink.events[-1].result == "DENIED"
    assert audit_sink.events[-1].subject_id == 101


def test_service_rejects_invalid_cursor_before_scope_or_fetch(fake_repo, audit_sink):
    service = ClinicalRetrievalService(
        fake_repo,
        DemoAssignmentProvider({"doctor-1": {101}}, set()),
        audit_sink,
        cursor_secret="s" * 32,
    )

    with pytest.raises(ClinicalScopeInvalid):
        service.get_laboratory_results(
            allowed_context(), ClinicalQuery(subject_id=101, cursor="invalid")
        )

    assert fake_repo.scope_calls == 0
    assert fake_repo.fetch_calls == []


def test_service_returns_bound_next_cursor(fake_repo, audit_sink):
    fake_repo.fetches["fetch_laboratory_results"] = RepositoryFetch(
        [],
        [],
        next_position=CursorPosition(
            event_time=datetime(2125, 1, 1, tzinfo=UTC),
            domain="labevents",
            source_key="9001",
        ),
        has_more=True,
    )
    service = ClinicalRetrievalService(
        fake_repo,
        DemoAssignmentProvider({"doctor-1": {101}}, set()),
        audit_sink,
        cursor_secret="s" * 32,
    )

    result = service.get_laboratory_results(allowed_context(), ClinicalQuery(subject_id=101))

    assert result.page.has_more is True
    assert result.page.next_cursor


def test_service_rejects_invalid_scope_before_fetch(assigned_service, fake_repo, audit_sink):
    """Removing the scope guard would permit a fetch for a mismatched encounter."""
    fake_repo.scope_is_valid = False

    with pytest.raises(ClinicalScopeInvalid):
        assigned_service.get_laboratory_results(
            allowed_context(), ClinicalQuery(subject_id=101, hadm_id=999999)
        )

    assert fake_repo.scope_calls == 1
    assert fake_repo.fetch_calls == []
    assert audit_sink.events[-1].result == "ERROR"


def test_service_marks_missing_source_partial(assigned_service, audit_sink):
    """Dropping unavailable-source status mapping would report a false success."""
    result = assigned_service.get_laboratory_results(allowed_context(), ClinicalQuery(subject_id=101))

    assert result.status == "PARTIAL"
    assert result.records[0].lineage.table == "labevents"
    assert "d_labitems" in " ".join(result.warnings)
    assert result.trace_id == TEST_TRACE_ID
    assert audit_sink.events[-1].result == "PARTIAL"


def test_service_marks_missing_dictionary_partial_from_sqlite_fixture(tmp_path):
    """Missing lab dictionary data must be explicit instead of silently looking complete."""
    db_path = tmp_path / "clinical.sqlite"
    create_mock_clinical_db(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute("DROP TABLE d_labitems")
        connection.commit()

    service = ClinicalRetrievalService(
        SQLiteClinicalRepository(str(db_path)),
        DemoAssignmentProvider({"doctor-1": {101}}, set()),
        InMemoryAuditSink(),
    )
    result = service.get_laboratory_results(allowed_context(), ClinicalQuery(subject_id=101))

    assert result.status == "PARTIAL"
    assert result.records
    assert "d_labitems" in " ".join(result.warnings)


def test_service_marks_unavailable_domain_not_loaded(assigned_service, fake_repo):
    """Treating an unloaded source as an empty result would hide data availability."""
    fake_repo.fetches["fetch_microbiology_results"] = RepositoryFetch([], ["microbiologyevents"])

    result = assigned_service.get_microbiology_results(allowed_context(), ClinicalQuery(subject_id=101))

    assert result.status == "NOT_LOADED"
    assert "microbiologyevents" in " ".join(result.warnings)


def test_service_preserves_empty_result_when_sources_are_available(assigned_service):
    """Mapping an ordinary empty fetch to NOT_LOADED would fail this test."""
    result = assigned_service.get_encounter_timeline(allowed_context(), ClinicalQuery(subject_id=101))

    assert result.status == "EMPTY"
    assert result.records == []
    assert result.warnings == []


@pytest.mark.parametrize(
    ("method_name", "repository_method"),
    [
        ("get_patient_overview", "fetch_patient_overview"),
        ("get_encounter_timeline", "fetch_encounter_timeline"),
        ("get_diagnoses_and_procedures", "fetch_diagnoses_and_procedures"),
        ("get_laboratory_results", "fetch_laboratory_results"),
        ("get_microbiology_results", "fetch_microbiology_results"),
        ("get_icu_events", "fetch_icu_events"),
    ],
)
def test_service_routes_each_domain_to_its_single_repository_fetch(
    assigned_service, fake_repo, method_name, repository_method
):
    """Changing a public method to fetch another clinical domain must fail this test."""
    result = getattr(assigned_service, method_name)(allowed_context(), ClinicalQuery(subject_id=101))

    assert fake_repo.fetch_calls == [repository_method]
    assert result.trace_id == TEST_TRACE_ID


def test_service_maps_sqlite_errors_without_exposing_database_text(assigned_service, fake_repo, audit_sink):
    """Letting a SQLite error cross the service boundary must fail this test."""
    fake_repo.fetches["fetch_microbiology_results"] = sqlite3.OperationalError(
        "no such table: restricted_clinical_values"
    )

    with pytest.raises(ClinicalDatabaseUnavailable) as error:
        assigned_service.get_microbiology_results(allowed_context(), ClinicalQuery(subject_id=101))

    assert str(error.value) == ""
    assert audit_sink.events[-1].result == "ERROR"


def test_service_maps_all_sqlite_database_errors_without_exposing_database_text(
    assigned_service, fake_repo, audit_sink
):
    """A non-operational SQLite database error must not escape as an HTTP 500."""
    fake_repo.fetches["fetch_microbiology_results"] = sqlite3.DatabaseError(
        "database disk image is malformed: raw clinical value"
    )

    with pytest.raises(ClinicalDatabaseUnavailable) as error:
        assigned_service.get_microbiology_results(allowed_context(), ClinicalQuery(subject_id=101))

    assert str(error.value) == ""
    assert audit_sink.events[-1].result == "ERROR"


def test_service_maps_timeout_errors(assigned_service, fake_repo, audit_sink):
    """Allowing a raw timeout to cross the service boundary must fail this test."""
    fake_repo.fetches["fetch_icu_events"] = TimeoutError("query exceeded 2 seconds")

    with pytest.raises(ClinicalQueryTimeout) as error:
        assigned_service.get_icu_events(allowed_context(), ClinicalQuery(subject_id=101, stay_id=7001))

    assert str(error.value) == ""
    assert audit_sink.events[-1].result == "ERROR"


def test_service_sanitizes_existing_query_timeout_messages(assigned_service, fake_repo, audit_sink):
    """Re-raising an existing timeout would expose its sensitive repository message."""
    fake_repo.fetches["fetch_icu_events"] = ClinicalQueryTimeout(
        "SELECT raw_value FROM restricted_clinical_values"
    )

    with pytest.raises(ClinicalQueryTimeout) as error:
        assigned_service.get_icu_events(allowed_context(), ClinicalQuery(subject_id=101, stay_id=7001))

    assert str(error.value) == ""
    assert error.value.__cause__ is None
    assert audit_sink.events[-1].result == "ERROR"
