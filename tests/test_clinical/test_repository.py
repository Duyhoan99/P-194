import sqlite3
from datetime import UTC, datetime

import pytest

from src.clinical.repository import SQLiteClinicalRepository
from src.clinical.schemas import ClinicalQuery
from tests.clinical_fixtures import create_mock_clinical_db


def test_repository_returns_lab_value_lineage_and_dictionary_source(tmp_path):
    """Removing the lab query or dictionary lineage should fail this test."""
    db_path = tmp_path / "clinical.sqlite"
    create_mock_clinical_db(db_path)

    repo = SQLiteClinicalRepository(str(db_path))
    result = repo.fetch_laboratory_results(ClinicalQuery(subject_id=101))

    assert [record.data["value"] for record in result.records] == ["1.2", "1.3"]
    assert result.records[0].lineage.table == "labevents"
    assert result.records[0].lineage.source_row_key == "labevent_id=9001"
    assert result.records[0].related_sources[0].table == "d_labitems"


def test_microbiology_lineage_uses_unique_microevent_ids(tmp_path):
    """Replacing unique microevent IDs with shared descriptive fields should fail this test."""
    db_path = tmp_path / "clinical.sqlite"
    create_mock_clinical_db(db_path)
    repo = SQLiteClinicalRepository(str(db_path))

    result = repo.fetch_microbiology_results(ClinicalQuery(subject_id=101))

    assert [record.lineage.source_row_key for record in result.records] == [
        "microevent_id=9101",
        "microevent_id=9102",
    ]


def test_repository_preserves_raw_source_timestamps_in_record_data(tmp_path):
    """Dropping source timestamps from domain data should fail this test."""
    db_path = tmp_path / "clinical.sqlite"
    create_mock_clinical_db(db_path)
    repo = SQLiteClinicalRepository(str(db_path))

    laboratory = repo.fetch_laboratory_results(ClinicalQuery(subject_id=101))
    microbiology = repo.fetch_microbiology_results(ClinicalQuery(subject_id=101))
    icu_events = repo.fetch_icu_events(ClinicalQuery(subject_id=101, stay_id=7001))

    assert laboratory.records[0].data["charttime"] == "2200-01-10 13:00:00"
    assert laboratory.records[0].data["storetime"] == "2200-01-10 13:05:00"
    assert microbiology.records[0].data["charttime"] == "2200-01-10 15:00:00"
    assert microbiology.records[0].data["storedate"] == "2200-01-10"
    assert microbiology.records[0].data["storetime"] == "2200-01-10 15:02:00"
    assert icu_events.records[0].data["intime"] == "2200-01-10 12:00:00"
    assert icu_events.records[1].data["charttime"] == "2200-01-10 16:00:00"
    assert icu_events.records[1].data["storetime"] == "2200-01-10 16:01:00"
    assert icu_events.records[2].data["charttime"] == "2200-01-10 17:00:00"
    assert icu_events.records[2].data["storetime"] == "2200-01-10 17:01:00"


def test_repository_exposes_only_a_read_only_connection(tmp_path):
    """Removing the read-only SQLite URI should make this write succeed."""
    db_path = tmp_path / "clinical.sqlite"
    create_mock_clinical_db(db_path)

    repo = SQLiteClinicalRepository(str(db_path))
    repo.fetch_patient_overview(ClinicalQuery(subject_id=101))

    with pytest.raises(sqlite3.OperationalError):
        repo.connection.execute("CREATE TABLE should_not_exist (id INTEGER)")


def test_repository_normalizes_aware_time_filters_for_naive_sqlite_timestamps(tmp_path):
    """Passing an aware time boundary through unchanged should exclude an equal source timestamp."""
    db_path = tmp_path / "clinical.sqlite"
    create_mock_clinical_db(db_path)
    repo = SQLiteClinicalRepository(str(db_path))

    result = repo.fetch_laboratory_results(
        ClinicalQuery(subject_id=101, from_time=datetime(2200, 1, 10, 13, tzinfo=UTC))
    )

    assert [record.lineage.source_row_key for record in result.records] == ["labevent_id=9001", "labevent_id=9002"]


def test_repository_preserves_lab_integrity_and_null_scope_ids(tmp_path):
    """Lab evidence must preserve source fields and keep missing encounter IDs null."""
    db_path = tmp_path / "clinical.sqlite"
    create_mock_clinical_db(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE labevents SET hadm_id = NULL, specimen_id = NULL WHERE labevent_id = 9002"
        )
        connection.commit()

    repo = SQLiteClinicalRepository(str(db_path))
    result = repo.fetch_laboratory_results(ClinicalQuery(subject_id=101))
    record = next(record for record in result.records if record.lineage.source_row_key == "labevent_id=9002")

    assert record.data["value"] == "1.3"
    assert record.data["valuenum"] == 1.3
    assert record.data["valueuom"] == "unit"
    assert record.data["ref_range_lower"] == 0.5
    assert record.data["ref_range_upper"] == 1.5
    assert record.data["charttime"] == "2200-01-10 14:00:00"
    assert record.data["specimen_id"] is None
    assert record.lineage.hadm_id is None
    assert record.lineage.stay_id is None
    assert record.lineage.source_row_key == "labevent_id=9002"


def test_repository_validates_hospital_and_icu_scope_against_subject(tmp_path):
    """Removing subject matching from scope validation should fail this test."""
    db_path = tmp_path / "clinical.sqlite"
    create_mock_clinical_db(db_path)
    repo = SQLiteClinicalRepository(str(db_path))

    assert repo.validate_scope(ClinicalQuery(subject_id=101, hadm_id=5001, stay_id=7001))
    assert not repo.validate_scope(ClinicalQuery(subject_id=101, hadm_id=5002))
    assert not repo.validate_scope(ClinicalQuery(subject_id=101, stay_id=9999))


def test_repository_reports_only_known_available_tables_and_missing_modules(tmp_path):
    """Returning arbitrary sqlite tables or wrong module status should fail this test."""
    db_path = tmp_path / "clinical.sqlite"
    create_mock_clinical_db(db_path)
    repo = SQLiteClinicalRepository(str(db_path))

    availability = repo.available_sources()

    assert {"patients", "labevents", "chartevents"} <= availability.available_tables
    assert "sqlite_sequence" not in availability.available_tables
    assert availability.unavailable_modules == []


def test_repository_fetches_each_domain_and_reports_absent_sources(tmp_path):
    """Dropping a domain query or its unavailable-source signal should fail this test."""
    db_path = tmp_path / "clinical.sqlite"
    create_mock_clinical_db(db_path)
    repo = SQLiteClinicalRepository(str(db_path))
    query = ClinicalQuery(subject_id=101, hadm_id=5001, stay_id=7001)

    overview = repo.fetch_patient_overview(query)
    timeline = repo.fetch_encounter_timeline(query)
    diagnoses = repo.fetch_diagnoses_and_procedures(query)
    microbiology = repo.fetch_microbiology_results(query)
    icu_events = repo.fetch_icu_events(query)

    assert [record.record_type for record in overview.records] == ["patient", "admission"]
    assert [record.record_type for record in timeline.records] == ["admission", "icu_stay"]
    assert timeline.unavailable_sources == ["transfers", "services"]
    assert [record.record_type for record in diagnoses.records] == ["diagnosis", "procedure"]
    assert diagnoses.records[0].related_sources[0].table == "d_icd_diagnoses"
    assert diagnoses.records[1].related_sources[0].table == "d_icd_procedures"
    assert diagnoses.unavailable_sources == ["hcpcsevents", "procedureevents"]
    assert microbiology.records[0].data["organism"] == "Synthetic organism"
    assert microbiology.records[0].lineage.table == "microbiologyevents"
    assert [record.record_type for record in icu_events.records] == ["icu_stay", "chart_event", "output_event"]
    assert icu_events.unavailable_sources == ["datetimeevents", "inputevents", "procedureevents"]
