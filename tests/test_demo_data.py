import sqlite3

from scripts.create_synthetic_demo import create_synthetic_demo_database


def test_synthetic_demo_has_expected_domains_without_raw_mimic_files(tmp_path):
    database_path = create_synthetic_demo_database(tmp_path / "synthetic_demo.db")

    with sqlite3.connect(database_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        patient_count = connection.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        admission = connection.execute("SELECT subject_id, hadm_id FROM admissions WHERE hadm_id = 201").fetchone()
        stay = connection.execute("SELECT subject_id, hadm_id, stay_id FROM icustays WHERE stay_id = 301").fetchone()
        lab_value = connection.execute("SELECT valuenum FROM labevents WHERE subject_id = 101").fetchone()[0]
        medication_statuses = [
            row[0] for row in connection.execute("SELECT source_status FROM medications ORDER BY medication_id")
        ]

    assert {"patients", "admissions", "labevents", "diagnoses_icd"} <= tables
    assert patient_count == 2
    assert admission == (101, 201)
    assert stay == (101, 201, 301)
    assert lab_value == 1.2
    assert medication_statuses == ["ACTIVE", "DISCONTINUED"]
