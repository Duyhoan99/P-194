import sqlite3
from src.clinical.repository import SQLiteClinicalRepository
from src.clinical.schemas import ClinicalQuery

repo = SQLiteClinicalRepository("mimic_demo.db")
query = ClinicalQuery(subject_id=10014729)

print("Scope Valid:", repo.validate_scope(query))

try:
    overview = repo.fetch_patient_overview(query)
    print("Overview:", overview.records)
except Exception as e:
    import traceback
    traceback.print_exc()

try:
    timeline = repo.fetch_encounter_timeline(query)
    print("Timeline:", len(timeline.records))
except Exception as e:
    import traceback
    traceback.print_exc()
