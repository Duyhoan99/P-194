"""Create the deterministic, synthetic-only clinical demo database."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def create_synthetic_demo_database(path: str | Path) -> Path:
    """Create a local SQLite demo database containing no source clinical records."""

    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_path.unlink(missing_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE patients (subject_id INTEGER PRIMARY KEY, gender TEXT NOT NULL, anchor_age INTEGER NOT NULL, anchor_year INTEGER NOT NULL, anchor_year_group TEXT NOT NULL, dod TEXT);
            CREATE TABLE admissions (subject_id INTEGER NOT NULL, hadm_id INTEGER PRIMARY KEY, admittime TEXT NOT NULL, dischtime TEXT, admission_type TEXT, admission_location TEXT, discharge_location TEXT, insurance TEXT, language TEXT, marital_status TEXT, race TEXT, edregtime TEXT, edouttime TEXT, hospital_expire_flag INTEGER);
            CREATE TABLE icustays (subject_id INTEGER NOT NULL, hadm_id INTEGER NOT NULL, stay_id INTEGER PRIMARY KEY, intime TEXT NOT NULL, outtime TEXT, first_careunit TEXT, last_careunit TEXT, los REAL);
            CREATE TABLE diagnoses_icd (subject_id INTEGER NOT NULL, hadm_id INTEGER NOT NULL, seq_num INTEGER NOT NULL, icd_code TEXT NOT NULL, icd_version INTEGER NOT NULL);
            CREATE TABLE d_icd_diagnoses (icd_code TEXT NOT NULL, icd_version INTEGER NOT NULL, long_title TEXT, PRIMARY KEY (icd_code, icd_version));
            CREATE TABLE procedures_icd (subject_id INTEGER NOT NULL, hadm_id INTEGER NOT NULL, seq_num INTEGER NOT NULL, chartdate TEXT NOT NULL, icd_code TEXT NOT NULL, icd_version INTEGER NOT NULL);
            CREATE TABLE d_icd_procedures (icd_code TEXT NOT NULL, icd_version INTEGER NOT NULL, long_title TEXT, PRIMARY KEY (icd_code, icd_version));
            CREATE TABLE labevents (labevent_id INTEGER PRIMARY KEY, subject_id INTEGER NOT NULL, hadm_id INTEGER, specimen_id INTEGER, itemid INTEGER NOT NULL, charttime TEXT, storetime TEXT, value TEXT, valuenum REAL, valueuom TEXT, ref_range_lower REAL, ref_range_upper REAL, flag TEXT, priority TEXT, comments TEXT);
            CREATE TABLE d_labitems (itemid INTEGER PRIMARY KEY, label TEXT, fluid TEXT, category TEXT);
            CREATE TABLE microbiologyevents (microevent_id INTEGER PRIMARY KEY, subject_id INTEGER NOT NULL, hadm_id INTEGER, micro_specimen_id INTEGER NOT NULL, chartdate TEXT, charttime TEXT, storedate TEXT, storetime TEXT, spec_type_desc TEXT, test_name TEXT, org_name TEXT, isolation TEXT, quantity TEXT, ab_name TEXT, dilution_text TEXT, dilution_comparison TEXT, dilution_value REAL, interpretation TEXT);
            CREATE TABLE medications (medication_id INTEGER PRIMARY KEY, subject_id INTEGER NOT NULL, hadm_id INTEGER NOT NULL, medication_name TEXT NOT NULL, source_status TEXT NOT NULL, recorded_at TEXT NOT NULL);
            """
        )
        connection.executemany(
            "INSERT INTO patients VALUES (?, ?, ?, ?, ?, ?)",
            [(101, "F", 55, 2200, "2200-2202", None), (102, "M", 63, 2201, "2200-2202", None)],
        )
        connection.executemany(
            "INSERT INTO admissions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    101,
                    201,
                    "2200-01-10 08:00:00",
                    "2200-01-12 10:00:00",
                    "EMERGENCY",
                    "DEMO",
                    "HOME",
                    "DEMO",
                    "ENGLISH",
                    "SINGLE",
                    "OTHER",
                    None,
                    None,
                    0,
                ),
                (
                    102,
                    202,
                    "2201-02-20 09:00:00",
                    "2201-02-21 11:00:00",
                    "ELECTIVE",
                    "DEMO",
                    "HOME",
                    "DEMO",
                    "ENGLISH",
                    "MARRIED",
                    "OTHER",
                    None,
                    None,
                    0,
                ),
            ],
        )
        connection.execute(
            "INSERT INTO icustays VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (101, 201, 301, "2200-01-10 12:00:00", "2200-01-11 12:00:00", "DEMO ICU", "DEMO ICU", 1.0),
        )
        connection.execute("INSERT INTO diagnoses_icd VALUES (?, ?, ?, ?, ?)", (101, 201, 1, "DEMO101", 10))
        connection.execute("INSERT INTO d_icd_diagnoses VALUES (?, ?, ?)", ("DEMO101", 10, "Synthetic diagnosis"))
        connection.execute(
            "INSERT INTO procedures_icd VALUES (?, ?, ?, ?, ?, ?)", (101, 201, 1, "2200-01-11", "DEMO201", 10)
        )
        connection.execute("INSERT INTO d_icd_procedures VALUES (?, ?, ?)", ("DEMO201", 10, "Synthetic procedure"))
        connection.execute("INSERT INTO d_labitems VALUES (?, ?, ?, ?)", (401, "Synthetic lab", "Blood", "Chemistry"))
        connection.execute(
            "INSERT INTO labevents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                501,
                101,
                201,
                601,
                401,
                "2200-01-10 13:00:00",
                "2200-01-10 13:05:00",
                "1.2",
                1.2,
                "unit",
                0.5,
                1.5,
                None,
                "ROUTINE",
                "Synthetic result",
            ),
        )
        connection.execute(
            "INSERT INTO microbiologyevents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                701,
                101,
                201,
                801,
                "2200-01-10",
                "2200-01-10 15:00:00",
                "2200-01-10",
                "2200-01-10 15:02:00",
                "Synthetic specimen",
                "Synthetic test",
                "Synthetic finding",
                None,
                None,
                None,
                None,
                None,
                None,
                "SYNTHETIC",
            ),
        )
        connection.executemany(
            "INSERT INTO medications VALUES (?, ?, ?, ?, ?, ?)",
            [
                (901, 101, 201, "Synthetic medication", "ACTIVE", "2200-01-10 18:00:00"),
                (902, 101, 201, "Synthetic medication", "DISCONTINUED", "2200-01-10 18:01:00"),
            ],
        )

    return database_path


if __name__ == "__main__":
    create_synthetic_demo_database("data/synthetic_demo.db")
