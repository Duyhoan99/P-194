import sqlite3

from scripts.check_clinical_indexes import main
from tests.clinical_fixtures import create_mock_clinical_db


def test_index_checker_is_read_only_and_reports_missing_indexes(tmp_path, capsys):
    db_path = tmp_path / "clinical.sqlite"
    create_mock_clinical_db(db_path)

    assert main([str(db_path)]) == 1
    output = capsys.readouterr().out

    assert "labevents" in output
    assert "1.2" not in output
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'clinical_%'"
        ).fetchall() == []


def test_index_checker_accepts_required_composite_indexes(tmp_path):
    db_path = tmp_path / "clinical.sqlite"
    create_mock_clinical_db(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE INDEX clinical_patients_subject ON patients(subject_id);
            CREATE INDEX clinical_admissions_scope ON admissions(subject_id, hadm_id);
            CREATE INDEX clinical_icustays_scope ON icustays(subject_id, hadm_id, stay_id);
            CREATE INDEX clinical_labevents_scope ON labevents(subject_id, hadm_id, charttime, labevent_id);
            CREATE INDEX clinical_chartevents_scope ON chartevents(subject_id, hadm_id, stay_id, charttime);
            """
        )
        connection.commit()

    assert main([str(db_path)]) == 0
