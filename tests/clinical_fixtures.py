"""Synthetic SQLite fixtures for clinical repository tests."""

import sqlite3
from pathlib import Path


def create_mock_clinical_db(path: Path) -> None:
    """Create a minimal, fully synthetic subset of the clinical schema."""

    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE patients (
                subject_id INTEGER PRIMARY KEY,
                gender TEXT NOT NULL,
                anchor_age INTEGER NOT NULL,
                anchor_year INTEGER NOT NULL,
                anchor_year_group TEXT NOT NULL,
                dod TEXT
            );
            CREATE TABLE admissions (
                subject_id INTEGER NOT NULL,
                hadm_id INTEGER PRIMARY KEY,
                admittime TEXT NOT NULL,
                dischtime TEXT,
                admission_type TEXT,
                admission_location TEXT,
                discharge_location TEXT,
                insurance TEXT,
                language TEXT,
                marital_status TEXT,
                race TEXT,
                edregtime TEXT,
                edouttime TEXT,
                hospital_expire_flag INTEGER
            );
            CREATE TABLE icustays (
                subject_id INTEGER NOT NULL,
                hadm_id INTEGER NOT NULL,
                stay_id INTEGER PRIMARY KEY,
                intime TEXT NOT NULL,
                outtime TEXT,
                first_careunit TEXT,
                last_careunit TEXT,
                los REAL
            );
            CREATE TABLE diagnoses_icd (
                subject_id INTEGER NOT NULL,
                hadm_id INTEGER NOT NULL,
                seq_num INTEGER NOT NULL,
                icd_code TEXT NOT NULL,
                icd_version INTEGER NOT NULL
            );
            CREATE TABLE d_icd_diagnoses (
                icd_code TEXT NOT NULL,
                icd_version INTEGER NOT NULL,
                long_title TEXT,
                PRIMARY KEY (icd_code, icd_version)
            );
            CREATE TABLE procedures_icd (
                subject_id INTEGER NOT NULL,
                hadm_id INTEGER NOT NULL,
                seq_num INTEGER NOT NULL,
                chartdate TEXT NOT NULL,
                icd_code TEXT NOT NULL,
                icd_version INTEGER NOT NULL
            );
            CREATE TABLE d_icd_procedures (
                icd_code TEXT NOT NULL,
                icd_version INTEGER NOT NULL,
                long_title TEXT,
                PRIMARY KEY (icd_code, icd_version)
            );
            CREATE TABLE labevents (
                labevent_id INTEGER PRIMARY KEY,
                subject_id INTEGER NOT NULL,
                hadm_id INTEGER,
                specimen_id INTEGER,
                itemid INTEGER NOT NULL,
                charttime TEXT,
                storetime TEXT,
                value TEXT,
                valuenum REAL,
                valueuom TEXT,
                ref_range_lower REAL,
                ref_range_upper REAL,
                flag TEXT,
                priority TEXT,
                comments TEXT
            );
            CREATE TABLE d_labitems (
                itemid INTEGER PRIMARY KEY,
                label TEXT,
                fluid TEXT,
                category TEXT
            );
            CREATE TABLE microbiologyevents (
                microevent_id INTEGER PRIMARY KEY,
                subject_id INTEGER NOT NULL,
                hadm_id INTEGER,
                micro_specimen_id INTEGER NOT NULL,
                chartdate TEXT,
                charttime TEXT,
                storedate TEXT,
                storetime TEXT,
                spec_type_desc TEXT,
                test_name TEXT,
                org_name TEXT,
                isolation TEXT,
                quantity TEXT,
                ab_name TEXT,
                dilution_text TEXT,
                dilution_comparison TEXT,
                dilution_value REAL,
                interpretation TEXT
            );
            CREATE TABLE chartevents (
                subject_id INTEGER NOT NULL,
                hadm_id INTEGER,
                stay_id INTEGER NOT NULL,
                charttime TEXT NOT NULL,
                storetime TEXT,
                itemid INTEGER NOT NULL,
                value TEXT,
                valuenum REAL,
                valueuom TEXT,
                warning INTEGER
            );
            CREATE TABLE outputevents (
                subject_id INTEGER NOT NULL,
                hadm_id INTEGER,
                stay_id INTEGER NOT NULL,
                charttime TEXT NOT NULL,
                storetime TEXT,
                itemid INTEGER NOT NULL,
                value REAL,
                valueuom TEXT
            );
            CREATE TABLE d_items (
                itemid INTEGER PRIMARY KEY,
                label TEXT,
                abbreviation TEXT,
                linksto TEXT,
                category TEXT,
                unitname TEXT,
                param_type TEXT,
                lownormalvalue REAL,
                highnormalvalue REAL
            );
            CREATE TABLE prescriptions (
                subject_id INTEGER NOT NULL,
                hadm_id INTEGER NOT NULL,
                pharmacy_id INTEGER NOT NULL,
                starttime TEXT,
                stoptime TEXT,
                drug TEXT,
                prod_strength TEXT,
                dose_val_rx TEXT,
                dose_unit_rx TEXT,
                form_rx TEXT,
                route TEXT
            );
            CREATE TABLE pharmacy (
                subject_id INTEGER NOT NULL,
                hadm_id INTEGER NOT NULL,
                pharmacy_id INTEGER NOT NULL,
                starttime TEXT,
                stoptime TEXT,
                medication TEXT,
                status TEXT,
                route TEXT,
                frequency TEXT
            );
            CREATE TABLE emar (
                subject_id INTEGER NOT NULL,
                hadm_id INTEGER NOT NULL,
                emar_id INTEGER PRIMARY KEY,
                charttime TEXT,
                medication TEXT,
                event_txt TEXT,
                scheduletime TEXT,
                storetime TEXT
            );
            """
        )
        connection.executemany(
            "INSERT INTO patients VALUES (?, ?, ?, ?, ?, ?)",
            [
                (101, "F", 55, 2200, "2200 - 2202", None),
                (202, "M", 63, 2201, "2200 - 2202", None),
            ],
        )
        connection.executemany(
            "INSERT INTO admissions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (101, 5001, "2200-01-10 08:00:00", "2200-01-12 10:00:00", "EMERGENCY", "EMERGENCY ROOM", "HOME", "SYNTHETIC", "ENGLISH", "SINGLE", "OTHER", None, None, 0),
                (202, 5002, "2201-02-20 09:00:00", "2201-02-21 11:00:00", "ELECTIVE", "PHYSICIAN REFERRAL", "HOME", "SYNTHETIC", "ENGLISH", "MARRIED", "OTHER", None, None, 0),
            ],
        )
        connection.execute(
            "INSERT INTO icustays VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (101, 5001, 7001, "2200-01-10 12:00:00", "2200-01-11 12:00:00", "MICU", "MICU", 1.0),
        )
        connection.execute("INSERT INTO diagnoses_icd VALUES (?, ?, ?, ?, ?)", (101, 5001, 1, "SYN101", 10))
        connection.execute("INSERT INTO d_icd_diagnoses VALUES (?, ?, ?)", ("SYN101", 10, "Synthetic diagnosis"))
        connection.execute("INSERT INTO procedures_icd VALUES (?, ?, ?, ?, ?, ?)", (101, 5001, 1, "2200-01-11", "PR101", 10))
        connection.execute("INSERT INTO d_icd_procedures VALUES (?, ?, ?)", ("PR101", 10, "Synthetic procedure"))
        connection.execute("INSERT INTO d_labitems VALUES (?, ?, ?, ?)", (3001, "Synthetic lab", "Blood", "Chemistry"))
        connection.executemany(
            "INSERT INTO labevents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (9001, 101, 5001, 8001, 3001, "2200-01-10 13:00:00", "2200-01-10 13:05:00", "1.2", 1.2, "unit", 0.5, 1.5, None, "ROUTINE", None),
                (9002, 101, 5001, 8002, 3001, "2200-01-10 14:00:00", "2200-01-10 14:05:00", "1.3", 1.3, "unit", 0.5, 1.5, None, "ROUTINE", None),
            ],
        )
        connection.executemany(
            """
            INSERT INTO microbiologyevents (
                microevent_id, subject_id, hadm_id, micro_specimen_id, chartdate, charttime,
                storedate, storetime, spec_type_desc, test_name, org_name, isolation, quantity,
                ab_name, dilution_text, dilution_comparison, dilution_value, interpretation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (9101, 101, 5001, 8101, "2200-01-10", "2200-01-10 15:00:00", "2200-01-10", "2200-01-10 15:02:00", "Blood", "Culture", "Synthetic organism", None, None, None, None, None, None, "POSITIVE"),
                (9102, 101, 5001, 8101, "2200-01-10", "2200-01-10 15:00:00", "2200-01-10", "2200-01-10 15:02:00", "Blood", "Culture", "Synthetic organism", None, None, None, None, None, None, "POSITIVE"),
            ],
        )
        connection.execute("INSERT INTO d_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (4001, "Synthetic vital", "SV", "chartevents", "Vitals", "unit", "Numeric", None, None))
        connection.execute("INSERT INTO d_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (4002, "Synthetic output", "SO", "outputevents", "Output", "mL", "Numeric", None, None))
        connection.execute("INSERT INTO chartevents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (101, 5001, 7001, "2200-01-10 16:00:00", "2200-01-10 16:01:00", 4001, "98", 98.0, "unit", 0))
        connection.execute("INSERT INTO outputevents VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (101, 5001, 7001, "2200-01-10 17:00:00", "2200-01-10 17:01:00", 4002, 250.0, "mL"))
        connection.execute(
            "INSERT INTO prescriptions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (101, 5001, 9101, "2200-01-10 18:00:00", "2200-01-11 18:00:00", "Synthetic drug", "10 mg", "10", "mg", "tablet", "PO"),
        )
        connection.execute(
            "INSERT INTO pharmacy VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (101, 5001, 9102, "2200-01-10 19:00:00", "2200-01-12 19:00:00", "Synthetic drug", "Discontinued", "PO", "daily"),
        )
        connection.execute(
            "INSERT INTO emar VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (101, 5001, 9201, "2200-01-10 20:00:00", "Synthetic drug", "Given", "2200-01-10 20:00:00", "2200-01-10 20:01:00"),
        )
        connection.commit()
    finally:
        connection.close()
