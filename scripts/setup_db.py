import sqlite3
from pathlib import Path

import pandas as pd


INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_patients_subject ON patients(subject_id)",
    "CREATE INDEX IF NOT EXISTS idx_admissions_subject_hadm ON admissions(subject_id, hadm_id)",
    "CREATE INDEX IF NOT EXISTS idx_transfers_subject_hadm_time ON transfers(subject_id, hadm_id, intime)",
    "CREATE INDEX IF NOT EXISTS idx_diagnoses_subject_hadm ON diagnoses_icd(subject_id, hadm_id)",
    "CREATE INDEX IF NOT EXISTS idx_procedures_subject_hadm ON procedures_icd(subject_id, hadm_id)",
    "CREATE INDEX IF NOT EXISTS idx_labs_subject_hadm_time ON labevents(subject_id, hadm_id, charttime)",
    "CREATE INDEX IF NOT EXISTS idx_micro_subject_hadm_time ON microbiologyevents(subject_id, hadm_id, charttime)",
    "CREATE INDEX IF NOT EXISTS idx_prescriptions_subject_hadm_time ON prescriptions(subject_id, hadm_id, starttime)",
    "CREATE INDEX IF NOT EXISTS idx_pharmacy_subject_hadm_time ON pharmacy(subject_id, hadm_id, starttime)",
    "CREATE INDEX IF NOT EXISTS idx_emar_subject_hadm_time ON emar(subject_id, hadm_id, charttime)",
    "CREATE INDEX IF NOT EXISTS idx_icustays_subject_hadm_stay ON icustays(subject_id, hadm_id, stay_id)",
    "CREATE INDEX IF NOT EXISTS idx_chartevents_subject_hadm_stay_time ON chartevents(subject_id, hadm_id, stay_id, charttime)",
    "CREATE INDEX IF NOT EXISTS idx_inputevents_subject_hadm_stay_time ON inputevents(subject_id, hadm_id, stay_id, starttime)",
)


def setup_mimic_demo_db(source_dir: str | Path | None = None, db_path: str | Path | None = None) -> Path:
    """Load the checked-in MIMIC demo CSVs into an indexed local SQLite database."""
    base_dir = Path(__file__).parent.parent
    data_dir = Path(source_dir) if source_dir is not None else base_dir / "mimic-iv-clinical-database-demo-2.2"
    database_path = Path(db_path) if db_path is not None else base_dir / "data" / "mimic_demo.db"

    if not data_dir.exists():
        print(f"Error: Data directory not found at {data_dir}")
        raise FileNotFoundError(data_dir)

    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_path.unlink(missing_ok=True)
    print(f"Creating database at {database_path}")
    conn = sqlite3.connect(database_path)

    for module in ("hosp", "icu"):
        module_dir = data_dir / module
        if not module_dir.exists():
            print(f"Warning: Module directory not found at {module_dir}")
            continue

        print(f"Processing module: {module}")
        for csv_file in sorted(module_dir.glob("*.csv")):
            table_name = csv_file.stem
            print(f"  -> Loading {csv_file.name} into table '{table_name}'...")

            try:
                # Read in chunks to handle potentially large files gracefully
                chunksize = 100000
                first_chunk = True
                for chunk in pd.read_csv(csv_file, chunksize=chunksize, low_memory=False):
                    if first_chunk:
                        chunk.to_sql(table_name, conn, if_exists='replace', index=False)
                        first_chunk = False
                    else:
                        chunk.to_sql(table_name, conn, if_exists='append', index=False)
                print(f"     Successfully loaded {table_name}.")
            except Exception as error:
                conn.close()
                raise RuntimeError(f"Could not load {csv_file.name}") from error

    for statement in INDEXES:
        try:
            conn.execute(statement)
        except sqlite3.OperationalError:
            # Optional MIMIC tables may be absent; retrieval reports them as unavailable.
            continue

    conn.close()
    print(f"Database setup complete. You can now connect to {database_path}")
    return database_path

if __name__ == "__main__":
    setup_mimic_demo_db()
