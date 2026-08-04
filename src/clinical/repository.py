"""Read-only, allow-listed SQLite retrieval for clinical source records."""

import sqlite3
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from src.clinical.availability import ALLOWED_SOURCE_TABLES, SourceAvailability, source_availability
from src.clinical.errors import ClinicalQueryTimeout
from src.clinical.pagination import CursorPosition
from src.clinical.schemas import ClinicalQuery, EvidenceRecord, SourceLineage


class RepositoryFetch:
    """Records returned by one repository domain plus unavailable source tables."""

    def __init__(
        self,
        records: list[EvidenceRecord],
        unavailable_sources: list[str],
        next_position: CursorPosition | None = None,
        has_more: bool = False,
    ) -> None:
        self.records = records
        self.unavailable_sources = unavailable_sources
        self.next_position = next_position
        self.has_more = has_more


class ClinicalRepository(Protocol):
    """Data access boundary used by the clinical retrieval service."""

    def validate_scope(self, query: ClinicalQuery) -> bool: ...

    def available_sources(self) -> SourceAvailability: ...

    def fetch_patient_overview(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch: ...

    def fetch_encounter_timeline(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch: ...

    def fetch_diagnoses_and_procedures(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch: ...

    def fetch_laboratory_results(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch: ...

    def fetch_microbiology_results(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch: ...

    def fetch_medications(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch: ...

    def fetch_patient_metrics(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch: ...

    def fetch_icu_events(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch: ...


class SQLiteClinicalRepository:
    """Clinical repository backed by a SQLite database opened in read-only mode."""

    def __init__(
        self,
        db_path: str,
        query_timeout_seconds: float = 2.0,
        source_dataset: str = "MIMIC-IV",
        source_version: str = "3.1",
    ) -> None:
        self._query_timeout_seconds = query_timeout_seconds
        self._source_dataset = source_dataset
        self._source_version = source_version
        database_uri = f"{Path(db_path).resolve().as_uri()}?mode=ro"
        self._connection = sqlite3.connect(database_uri, uri=True, timeout=query_timeout_seconds)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA query_only = ON")
        self._tables = self._load_allow_listed_tables()
        self._table_columns = self._load_table_columns()

    @property
    def connection(self) -> sqlite3.Connection:
        """Expose the read-only connection for narrowly scoped diagnostics."""

        return self._connection

    def close(self) -> None:
        """Close the read-only database connection."""

        self._connection.close()

    def validate_scope(self, query: ClinicalQuery) -> bool:
        """Fail closed unless every requested identifier belongs to the subject."""

        if "patients" not in self._tables or not self._exists(
            "SELECT 1 FROM patients WHERE subject_id = ? LIMIT 1", (query.subject_id,)
        ):
            return False
        if query.hadm_id is not None and (
            "admissions" not in self._tables
            or not self._exists(
                "SELECT 1 FROM admissions WHERE subject_id = ? AND hadm_id = ? LIMIT 1",
                (query.subject_id, query.hadm_id),
            )
        ):
            return False
        if query.stay_id is not None and (
            "icustays" not in self._tables
            or not self._exists(
                "SELECT 1 FROM icustays WHERE subject_id = ? AND stay_id = ? LIMIT 1",
                (query.subject_id, query.stay_id),
            )
        ):
            return False
        if query.hadm_id is not None and query.stay_id is not None and not self._exists(
            "SELECT 1 FROM icustays WHERE subject_id = ? AND hadm_id = ? AND stay_id = ? LIMIT 1",
            (query.subject_id, query.hadm_id, query.stay_id),
        ):
            return False
        return True

    def available_sources(self) -> SourceAvailability:
        """Return only the known source tables that are present in the database."""

        return source_availability(self._tables)

    def fetch_patient_overview(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch:
        records: list[EvidenceRecord] = []
        unavailable: list[str] = []
        if "patients" not in self._tables:
            unavailable.append("patients")
        else:
            rows = self._execute(
                """
                SELECT subject_id, gender, anchor_age, anchor_year, anchor_year_group, dod
                FROM patients
                WHERE subject_id = ?
                ORDER BY subject_id DESC
                LIMIT ?
                """,
                (query.subject_id, query.limit + 1),
            )
            for row in rows:
                records.append(
                    self._record(
                        "patient",
                        {key: row[key] for key in ("gender", "anchor_age", "anchor_year", "anchor_year_group", "dod")},
                        row,
                        module="hosp",
                        table="patients",
                        source_key=f"subject_id={row['subject_id']}",
                    )
                )
        records.extend(self._admission_records(query, unavailable))
        return self._fetch(records, unavailable, query.limit, cursor_position)

    def fetch_encounter_timeline(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch:
        unavailable: list[str] = []
        records = self._admission_records(query, unavailable)
        records.extend(self._timeline_records(query, unavailable))
        return self._fetch(records, unavailable, query.limit, cursor_position)

    def fetch_diagnoses_and_procedures(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch:
        records: list[EvidenceRecord] = []
        unavailable: list[str] = []
        records.extend(self._diagnosis_records(query, unavailable))
        records.extend(self._procedure_records(query, unavailable))
        records.extend(self._hcpcs_records(query, unavailable))
        records.extend(self._procedure_event_records(query, unavailable))
        return self._fetch(records, unavailable, query.limit, cursor_position)

    def fetch_laboratory_results(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch:
        unavailable: list[str] = []
        if "labevents" not in self._tables:
            return RepositoryFetch(records=[], unavailable_sources=["labevents"])

        dictionary_loaded = "d_labitems" in self._tables
        if not dictionary_loaded:
            unavailable.append("d_labitems")
        dictionary_join = "LEFT JOIN d_labitems AS dictionary ON event.itemid = dictionary.itemid" if dictionary_loaded else ""
        dictionary_columns = "dictionary.label, dictionary.fluid, dictionary.category," if dictionary_loaded else "NULL AS label, NULL AS fluid, NULL AS category,"
        rows = self._execute(
            f"""
            SELECT event.subject_id, event.hadm_id, event.labevent_id, event.specimen_id, event.itemid,
                    event.charttime, COALESCE(event.charttime, event.storetime) AS event_time, event.storetime, event.value, event.valuenum,
                   event.valueuom, event.ref_range_lower, event.ref_range_upper, event.flag,
                   {dictionary_columns}
                   event.labevent_id AS source_key
            FROM labevents AS event
            {dictionary_join}
            WHERE event.subject_id = ?
              AND (? IS NULL OR event.hadm_id = ?)
              AND (? IS NULL OR COALESCE(event.charttime, event.storetime) >= ?)
              AND (? IS NULL OR COALESCE(event.charttime, event.storetime) <= ?)
            ORDER BY COALESCE(event.charttime, event.storetime) DESC, event.labevent_id DESC
            LIMIT ?
            """,
            self._hadm_time_params(query),
        )
        records = [
            self._record(
                "lab",
                {
                    key: row[key]
                    for key in (
                        "specimen_id",
                        "itemid",
                        "charttime",
                        "storetime",
                        "label",
                        "fluid",
                        "category",
                        "value",
                        "valuenum",
                        "valueuom",
                        "ref_range_lower",
                        "ref_range_upper",
                        "flag",
                    )
                },
                row,
                module="hosp",
                table="labevents",
                source_key=f"labevent_id={row['source_key']}",
                related_sources=[
                    self._dictionary_lineage(row, "hosp", "d_labitems", f"itemid={row['itemid']}")
                ]
                if dictionary_loaded
                else [],
            )
            for row in rows
        ]
        return self._fetch(records, unavailable, query.limit, cursor_position)

    def fetch_microbiology_results(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch:
        if "microbiologyevents" not in self._tables:
            return RepositoryFetch(records=[], unavailable_sources=["microbiologyevents"])
        isolation_column = "isolation" if "isolation" in self._table_columns.get("microbiologyevents", set()) else "isolate_num"
        rows = self._execute(
            f"""
            SELECT microevent_id, subject_id, hadm_id, micro_specimen_id, chartdate, charttime,
                    COALESCE(charttime, storetime) AS event_time, storedate, storetime, spec_type_desc, test_name, org_name,
                    {isolation_column} AS isolation, quantity, ab_name,
                   dilution_text, dilution_comparison, dilution_value, interpretation
            FROM microbiologyevents
            WHERE subject_id = ?
              AND (? IS NULL OR hadm_id = ?)
              AND (? IS NULL OR COALESCE(charttime, storetime) >= ?)
              AND (? IS NULL OR COALESCE(charttime, storetime) <= ?)
            ORDER BY COALESCE(charttime, storetime) DESC, micro_specimen_id DESC, test_name DESC, org_name DESC, microevent_id DESC
            LIMIT ?
            """,
            self._hadm_time_params(query),
        )
        records = [
            self._record(
                "microbiology",
                {
                    "microevent_id": row["microevent_id"],
                    "micro_specimen_id": row["micro_specimen_id"],
                    "chartdate": row["chartdate"],
                    "charttime": row["charttime"],
                    "storedate": row["storedate"],
                    "storetime": row["storetime"],
                    "specimen": row["spec_type_desc"],
                    "test": row["test_name"],
                    "organism": row["org_name"],
                    "isolation": row["isolation"],
                    "quantity": row["quantity"],
                    "antibiotic": row["ab_name"],
                    "dilution_text": row["dilution_text"],
                    "dilution_comparison": row["dilution_comparison"],
                    "dilution_value": row["dilution_value"],
                    "interpretation": row["interpretation"],
                },
                row,
                module="hosp",
                table="microbiologyevents",
                source_key=f"microevent_id={row['microevent_id']}",
            )
            for row in rows
        ]
        return self._fetch(records, [], query.limit, cursor_position)

    def fetch_medications(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch:
        unavailable: list[str] = []
        records: list[EvidenceRecord] = []
        records.extend(self._prescription_records(query, unavailable))
        records.extend(self._pharmacy_records(query, unavailable))
        records.extend(self._emar_records(query, unavailable))
        records.extend(self._input_medication_records(query, unavailable))
        return self._fetch(records, unavailable, query.limit, cursor_position)

    def fetch_patient_metrics(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch:
        if "omr" not in self._tables:
            return RepositoryFetch([], ["omr"])
        rows = self._execute(
            """
            SELECT subject_id, chartdate AS event_time, chartdate, seq_num, result_name, result_value
            FROM omr
            WHERE subject_id = ? AND (? IS NULL OR chartdate >= ?) AND (? IS NULL OR chartdate <= ?)
            ORDER BY chartdate DESC, seq_num DESC, result_name DESC
            LIMIT ?
            """,
            (query.subject_id, self._time_value(query.from_time), self._time_value(query.from_time),
             self._time_value(query.to_time), self._time_value(query.to_time), query.limit + 1),
        )
        records = [
            self._record(
                "metric",
                {key: row[key] for key in ("chartdate", "seq_num", "result_name", "result_value")},
                row,
                module="hosp",
                table="omr",
                source_key=self._composite_key(row, ("subject_id", "chartdate", "seq_num", "result_name")),
            )
            for row in rows
        ]
        return self._fetch(records, [], query.limit, cursor_position)

    def _prescription_records(self, query: ClinicalQuery, unavailable: list[str]) -> list[EvidenceRecord]:
        if "prescriptions" not in self._tables:
            unavailable.append("prescriptions")
            return []
        rows = self._execute(
            """
            SELECT subject_id, hadm_id, pharmacy_id, starttime AS event_time, starttime, stoptime,
                   drug, prod_strength, dose_val_rx, dose_unit_rx, form_rx, route
            FROM prescriptions
            WHERE subject_id = ? AND (? IS NULL OR hadm_id = ?)
              AND (? IS NULL OR starttime >= ?) AND (? IS NULL OR starttime <= ?)
            ORDER BY starttime DESC, pharmacy_id DESC
            LIMIT ?
            """,
            self._hadm_time_params(query),
        )
        return [
            self._record(
                "medication",
                {**{key: row[key] for key in ("drug", "prod_strength", "dose_val_rx", "dose_unit_rx", "form_rx", "route", "starttime", "stoptime")},
                 "medication": row["drug"], "source_status": "PRESCRIBED"},
                row,
                module="hosp",
                table="prescriptions",
                source_key=self._composite_key(
                    row, ("subject_id", "hadm_id", "pharmacy_id", "event_time", "drug", "route")
                ),
            )
            for row in rows
        ]

    def _pharmacy_records(self, query: ClinicalQuery, unavailable: list[str]) -> list[EvidenceRecord]:
        if "pharmacy" not in self._tables:
            unavailable.append("pharmacy")
            return []
        rows = self._execute(
            """
            SELECT subject_id, hadm_id, pharmacy_id, starttime AS event_time, starttime, stoptime,
                   medication, status, route, frequency
            FROM pharmacy
            WHERE subject_id = ? AND (? IS NULL OR hadm_id = ?)
              AND (? IS NULL OR starttime >= ?) AND (? IS NULL OR starttime <= ?)
            ORDER BY starttime DESC, pharmacy_id DESC
            LIMIT ?
            """,
            self._hadm_time_params(query),
        )
        return [
            self._record(
                "medication",
                {**{key: row[key] for key in ("medication", "status", "route", "frequency", "starttime", "stoptime")},
                 "source_status": self._medication_status(row["status"], "PRESCRIBED")},
                row,
                module="hosp",
                table="pharmacy",
                source_key=self._composite_key(
                    row, ("subject_id", "hadm_id", "pharmacy_id", "event_time", "medication", "status")
                ),
            )
            for row in rows
        ]

    def _emar_records(self, query: ClinicalQuery, unavailable: list[str]) -> list[EvidenceRecord]:
        if "emar" not in self._tables:
            unavailable.append("emar")
            return []
        rows = self._execute(
            """
            SELECT subject_id, hadm_id, emar_id, charttime AS event_time, charttime,
                   medication, event_txt, scheduletime, storetime
            FROM emar
            WHERE subject_id = ? AND (? IS NULL OR hadm_id = ?)
              AND (? IS NULL OR charttime >= ?) AND (? IS NULL OR charttime <= ?)
            ORDER BY charttime DESC, emar_id DESC
            LIMIT ?
            """,
            self._hadm_time_params(query),
        )
        return [
            self._record(
                "medication",
                {**{key: row[key] for key in ("medication", "event_txt", "charttime", "scheduletime", "storetime")},
                 "source_status": self._medication_status(row["event_txt"], "UNKNOWN_STATUS")},
                row,
                module="hosp",
                table="emar",
                source_key=f"emar_id={row['emar_id']}",
            )
            for row in rows
        ]

    def _input_medication_records(self, query: ClinicalQuery, unavailable: list[str]) -> list[EvidenceRecord]:
        if "inputevents" not in self._tables:
            unavailable.append("inputevents")
            return []
        rows = self._execute(
            """
            SELECT subject_id, hadm_id, stay_id, starttime AS event_time, starttime, endtime,
                   storetime, itemid, amount, amountuom, rate, rateuom, statusdescription
            FROM inputevents
            WHERE subject_id = ? AND (? IS NULL OR hadm_id = ?) AND (? IS NULL OR stay_id = ?)
              AND (? IS NULL OR starttime >= ?) AND (? IS NULL OR starttime <= ?)
            ORDER BY starttime DESC, itemid DESC
            LIMIT ?
            """,
            self._hadm_stay_time_params(query),
        )
        return [
            self._record(
                "medication",
                {**{key: row[key] for key in ("itemid", "starttime", "endtime", "storetime", "amount", "amountuom", "rate", "rateuom", "statusdescription")},
                 "source_status": "ADMINISTERED"},
                row,
                module="icu",
                table="inputevents",
                source_key=self._composite_key(row, ("subject_id", "hadm_id", "stay_id", "event_time", "itemid", "storetime")),
            )
            for row in rows
        ]

    @staticmethod
    def _medication_status(value: Any, default: str) -> str:
        text = str(value or "").casefold()
        if any(token in text for token in ("discontinu", "stopped", "cancel")):
            return "DISCONTINUED"
        if any(token in text for token in ("given", "administered", "complete")) and "not given" not in text:
            return "ADMINISTERED"
        return default

    def fetch_icu_events(
        self, query: ClinicalQuery, cursor_position: CursorPosition | None = None
    ) -> RepositoryFetch:
        unavailable: list[str] = []
        records: list[EvidenceRecord] = []
        records.extend(self._icu_stay_records(query, unavailable))
        records.extend(self._chart_event_records(query, unavailable))
        records.extend(self._datetime_event_records(query, unavailable))
        records.extend(self._input_event_records(query, unavailable))
        records.extend(self._output_event_records(query, unavailable))
        records.extend(self._procedure_event_records(query, unavailable))
        return self._fetch(records, unavailable, query.limit, cursor_position)

    def _admission_records(self, query: ClinicalQuery, unavailable: list[str]) -> list[EvidenceRecord]:
        if "admissions" not in self._tables:
            unavailable.append("admissions")
            return []
        rows = self._execute(
            """
            SELECT subject_id, hadm_id, admittime AS event_time, dischtime, admission_type,
                   admission_location, discharge_location, insurance, language, marital_status,
                   race, edregtime, edouttime, hospital_expire_flag
            FROM admissions
            WHERE subject_id = ? AND (? IS NULL OR hadm_id = ?)
            ORDER BY admittime DESC, hadm_id DESC
            LIMIT ?
            """,
            (query.subject_id, query.hadm_id, query.hadm_id, query.limit + 1),
        )
        return [
            self._record(
                "admission",
                {
                    key: row[key]
                    for key in (
                        "dischtime",
                        "admission_type",
                        "admission_location",
                        "discharge_location",
                        "insurance",
                        "language",
                        "marital_status",
                        "race",
                        "edregtime",
                        "edouttime",
                        "hospital_expire_flag",
                    )
                },
                row,
                module="hosp",
                table="admissions",
                source_key=f"hadm_id={row['hadm_id']}",
            )
            for row in rows
        ]

    def _timeline_records(self, query: ClinicalQuery, unavailable: list[str]) -> list[EvidenceRecord]:
        records = self._icu_stay_records(query, unavailable)
        if "transfers" not in self._tables:
            unavailable.append("transfers")
        else:
            rows = self._execute(
                """
                SELECT subject_id, hadm_id, transfer_id, eventtype, careunit, intime AS event_time, outtime
                FROM transfers
                WHERE subject_id = ? AND (? IS NULL OR hadm_id = ?)
                  AND (? IS NULL OR intime >= ?) AND (? IS NULL OR intime <= ?)
                ORDER BY intime DESC, transfer_id DESC
                LIMIT ?
                """,
                self._hadm_time_params(query),
            )
            records.extend(
                self._record(
                    "transfer",
                    {key: row[key] for key in ("eventtype", "careunit", "outtime")},
                    row,
                    module="hosp",
                    table="transfers",
                    source_key=f"transfer_id={row['transfer_id']}",
                )
                for row in rows
            )
        if "services" not in self._tables:
            unavailable.append("services")
        else:
            rows = self._execute(
                """
                SELECT subject_id, hadm_id, transfertime AS event_time, prev_service, curr_service
                FROM services
                WHERE subject_id = ? AND (? IS NULL OR hadm_id = ?)
                  AND (? IS NULL OR transfertime >= ?) AND (? IS NULL OR transfertime <= ?)
                ORDER BY transfertime DESC, hadm_id DESC, curr_service DESC
                LIMIT ?
                """,
                self._hadm_time_params(query),
            )
            records.extend(
                self._record(
                    "service",
                    {key: row[key] for key in ("prev_service", "curr_service")},
                    row,
                    module="hosp",
                    table="services",
                    source_key=self._composite_key(row, ("subject_id", "hadm_id", "event_time", "curr_service")),
                )
                for row in rows
            )
        return records

    def _diagnosis_records(self, query: ClinicalQuery, unavailable: list[str]) -> list[EvidenceRecord]:
        if "diagnoses_icd" not in self._tables:
            unavailable.append("diagnoses_icd")
            return []
        dictionary_loaded = "d_icd_diagnoses" in self._tables
        if not dictionary_loaded:
            unavailable.append("d_icd_diagnoses")
        join = "LEFT JOIN d_icd_diagnoses AS dictionary ON event.icd_code = dictionary.icd_code AND event.icd_version = dictionary.icd_version" if dictionary_loaded else ""
        title = "dictionary.long_title" if dictionary_loaded else "NULL AS long_title"
        rows = self._execute(
            f"""
            SELECT event.subject_id, event.hadm_id, event.seq_num, event.icd_code, event.icd_version,
                   {title}
            FROM diagnoses_icd AS event
            {join}
            WHERE event.subject_id = ? AND (? IS NULL OR event.hadm_id = ?)
            ORDER BY event.hadm_id DESC, event.seq_num DESC, event.icd_code DESC, event.icd_version DESC
            LIMIT ?
            """,
            (query.subject_id, query.hadm_id, query.hadm_id, query.limit + 1),
        )
        return [
            self._record(
                "diagnosis",
                {key: row[key] for key in ("seq_num", "icd_code", "icd_version", "long_title")},
                row,
                module="hosp",
                table="diagnoses_icd",
                source_key=self._composite_key(row, ("subject_id", "hadm_id", "seq_num", "icd_code", "icd_version")),
                related_sources=[
                    self._dictionary_lineage(
                        row,
                        "hosp",
                        "d_icd_diagnoses",
                        f"icd_code={row['icd_code']}|icd_version={row['icd_version']}",
                    )
                ]
                if dictionary_loaded
                else [],
            )
            for row in rows
        ]

    def _procedure_records(self, query: ClinicalQuery, unavailable: list[str]) -> list[EvidenceRecord]:
        if "procedures_icd" not in self._tables:
            unavailable.append("procedures_icd")
            return []
        dictionary_loaded = "d_icd_procedures" in self._tables
        if not dictionary_loaded:
            unavailable.append("d_icd_procedures")
        join = "LEFT JOIN d_icd_procedures AS dictionary ON event.icd_code = dictionary.icd_code AND event.icd_version = dictionary.icd_version" if dictionary_loaded else ""
        title = "dictionary.long_title" if dictionary_loaded else "NULL AS long_title"
        rows = self._execute(
            f"""
            SELECT event.subject_id, event.hadm_id, event.seq_num, event.chartdate AS event_time,
                   event.icd_code, event.icd_version, {title}
            FROM procedures_icd AS event
            {join}
            WHERE event.subject_id = ? AND (? IS NULL OR event.hadm_id = ?)
              AND (? IS NULL OR event.chartdate >= ?) AND (? IS NULL OR event.chartdate <= ?)
            ORDER BY event.chartdate DESC, event.hadm_id DESC, event.seq_num DESC, event.icd_code DESC
            LIMIT ?
            """,
            self._hadm_time_params(query),
        )
        return [
            self._record(
                "procedure",
                {key: row[key] for key in ("seq_num", "icd_code", "icd_version", "long_title")},
                row,
                module="hosp",
                table="procedures_icd",
                source_key=self._composite_key(row, ("subject_id", "hadm_id", "seq_num", "icd_code", "icd_version")),
                related_sources=[
                    self._dictionary_lineage(
                        row,
                        "hosp",
                        "d_icd_procedures",
                        f"icd_code={row['icd_code']}|icd_version={row['icd_version']}",
                    )
                ]
                if dictionary_loaded
                else [],
            )
            for row in rows
        ]

    def _hcpcs_records(self, query: ClinicalQuery, unavailable: list[str]) -> list[EvidenceRecord]:
        if "hcpcsevents" not in self._tables:
            unavailable.append("hcpcsevents")
            return []
        dictionary_loaded = "d_hcpcs" in self._tables
        if not dictionary_loaded:
            unavailable.append("d_hcpcs")
        join = "LEFT JOIN d_hcpcs AS dictionary ON event.hcpcs_cd = dictionary.code" if dictionary_loaded else ""
        description = "dictionary.long_description" if dictionary_loaded else "NULL AS long_description"
        rows = self._execute(
            f"""
            SELECT event.subject_id, event.hadm_id, event.chartdate AS event_time, event.seq_num,
                   event.hcpcs_cd, {description}
            FROM hcpcsevents AS event
            {join}
            WHERE event.subject_id = ? AND (? IS NULL OR event.hadm_id = ?)
              AND (? IS NULL OR event.chartdate >= ?) AND (? IS NULL OR event.chartdate <= ?)
            ORDER BY event.chartdate DESC, event.hadm_id DESC, event.seq_num DESC, event.hcpcs_cd DESC
            LIMIT ?
            """,
            self._hadm_time_params(query),
        )
        return [
            self._record(
                "hcpcs",
                {key: row[key] for key in ("seq_num", "hcpcs_cd", "long_description")},
                row,
                module="hosp",
                table="hcpcsevents",
                source_key=self._composite_key(row, ("subject_id", "hadm_id", "seq_num", "hcpcs_cd")),
                related_sources=[self._dictionary_lineage(row, "hosp", "d_hcpcs", f"code={row['hcpcs_cd']}")]
                if dictionary_loaded
                else [],
            )
            for row in rows
        ]

    def _icu_stay_records(self, query: ClinicalQuery, unavailable: list[str]) -> list[EvidenceRecord]:
        if "icustays" not in self._tables:
            unavailable.append("icustays")
            return []
        rows = self._execute(
            """
            SELECT subject_id, hadm_id, stay_id, intime, intime AS event_time, outtime, first_careunit,
                   last_careunit, los
            FROM icustays
            WHERE subject_id = ? AND (? IS NULL OR hadm_id = ?) AND (? IS NULL OR stay_id = ?)
              AND (? IS NULL OR intime >= ?) AND (? IS NULL OR intime <= ?)
            ORDER BY intime DESC, stay_id DESC
            LIMIT ?
            """,
            self._hadm_stay_time_params(query),
        )
        return [
            self._record(
                "icu_stay",
                {key: row[key] for key in ("intime", "outtime", "first_careunit", "last_careunit", "los")},
                row,
                module="icu",
                table="icustays",
                source_key=f"stay_id={row['stay_id']}",
            )
            for row in rows
        ]

    def _chart_event_records(self, query: ClinicalQuery, unavailable: list[str]) -> list[EvidenceRecord]:
        return self._item_event_records(
            query,
            unavailable,
            table="chartevents",
            record_type="chart_event",
            value_columns=("value", "valuenum", "valueuom", "warning"),
        )

    def _datetime_event_records(self, query: ClinicalQuery, unavailable: list[str]) -> list[EvidenceRecord]:
        return self._item_event_records(
            query,
            unavailable,
            table="datetimeevents",
            record_type="datetime_event",
            value_columns=("value",),
        )

    def _output_event_records(self, query: ClinicalQuery, unavailable: list[str]) -> list[EvidenceRecord]:
        return self._item_event_records(
            query,
            unavailable,
            table="outputevents",
            record_type="output_event",
            value_columns=("value", "valueuom"),
        )

    def _item_event_records(
        self,
        query: ClinicalQuery,
        unavailable: list[str],
        *,
        table: str,
        record_type: str,
        value_columns: tuple[str, ...],
    ) -> list[EvidenceRecord]:
        if table not in self._tables:
            unavailable.append(table)
            return []
        dictionary_loaded = "d_items" in self._tables
        if not dictionary_loaded:
            unavailable.append("d_items")
        join = "LEFT JOIN d_items AS dictionary ON event.itemid = dictionary.itemid" if dictionary_loaded else ""
        label = "dictionary.label" if dictionary_loaded else "NULL AS label"
        selected_values = ", ".join(f"event.{column}" for column in value_columns)
        rows = self._execute(
            f"""
                    SELECT event.subject_id, event.hadm_id, event.stay_id, event.charttime,
                           COALESCE(event.charttime, event.storetime) AS event_time,
                   event.storetime, event.itemid, {selected_values}, {label}
            FROM {table} AS event
            {join}
            WHERE event.subject_id = ? AND (? IS NULL OR event.hadm_id = ?) AND (? IS NULL OR event.stay_id = ?)
              AND (? IS NULL OR COALESCE(event.charttime, event.storetime) >= ?)
              AND (? IS NULL OR COALESCE(event.charttime, event.storetime) <= ?)
            ORDER BY COALESCE(event.charttime, event.storetime) DESC,
                     event.subject_id DESC, event.hadm_id DESC, event.stay_id DESC,
                     event.itemid DESC, event.storetime DESC
            LIMIT ?
            """,
            self._hadm_stay_time_params(query),
        )
        return [
            self._record(
                record_type,
                {key: row[key] for key in ("itemid", "label", "charttime", "storetime", *value_columns)},
                row,
                module="icu",
                table=table,
                source_key=self._composite_key(
                    row,
                    (
                        "subject_id",
                        "hadm_id",
                        "stay_id",
                        "event_time",
                        "itemid",
                        "storetime",
                        *value_columns,
                    ),
                ),
                related_sources=[self._dictionary_lineage(row, "icu", "d_items", f"itemid={row['itemid']}")]
                if dictionary_loaded
                else [],
            )
            for row in rows
        ]

    def _input_event_records(self, query: ClinicalQuery, unavailable: list[str]) -> list[EvidenceRecord]:
        if "inputevents" not in self._tables:
            unavailable.append("inputevents")
            return []
        dictionary_loaded = "d_items" in self._tables
        if not dictionary_loaded:
            unavailable.append("d_items")
        join = "LEFT JOIN d_items AS dictionary ON event.itemid = dictionary.itemid" if dictionary_loaded else ""
        label = "dictionary.label" if dictionary_loaded else "NULL AS label"
        rows = self._execute(
            f"""
                    SELECT event.subject_id, event.hadm_id, event.stay_id, event.starttime,
                           COALESCE(event.starttime, event.storetime) AS event_time,
                   event.endtime, event.storetime, event.itemid, event.amount, event.amountuom,
                   event.rate, event.rateuom, {label}
            FROM inputevents AS event
            {join}
            WHERE event.subject_id = ? AND (? IS NULL OR event.hadm_id = ?) AND (? IS NULL OR event.stay_id = ?)
              AND (? IS NULL OR COALESCE(event.starttime, event.storetime) >= ?)
              AND (? IS NULL OR COALESCE(event.starttime, event.storetime) <= ?)
            ORDER BY COALESCE(event.starttime, event.storetime) DESC,
                     event.subject_id DESC, event.hadm_id DESC, event.stay_id DESC,
                     event.itemid DESC, event.storetime DESC
            LIMIT ?
            """,
            self._hadm_stay_time_params(query),
        )
        return [
            self._record(
                "input_event",
                {
                    key: row[key]
                    for key in ("itemid", "label", "starttime", "endtime", "storetime", "amount", "amountuom", "rate", "rateuom")
                },
                row,
                module="icu",
                table="inputevents",
                source_key=self._composite_key(
                    row,
                    (
                        "subject_id",
                        "hadm_id",
                        "stay_id",
                        "event_time",
                        "itemid",
                        "storetime",
                        "amount",
                        "amountuom",
                        "rate",
                        "rateuom",
                    ),
                ),
                related_sources=[self._dictionary_lineage(row, "icu", "d_items", f"itemid={row['itemid']}")]
                if dictionary_loaded
                else [],
            )
            for row in rows
        ]

    def _procedure_event_records(self, query: ClinicalQuery, unavailable: list[str]) -> list[EvidenceRecord]:
        if "procedureevents" not in self._tables:
            unavailable.append("procedureevents")
            return []
        dictionary_loaded = "d_items" in self._tables
        if not dictionary_loaded:
            unavailable.append("d_items")
        join = "LEFT JOIN d_items AS dictionary ON event.itemid = dictionary.itemid" if dictionary_loaded else ""
        label = "dictionary.label" if dictionary_loaded else "NULL AS label"
        rows = self._execute(
            f"""
                    SELECT event.subject_id, event.hadm_id, event.stay_id, event.starttime,
                           COALESCE(event.starttime, event.storetime) AS event_time,
                   event.endtime, event.storetime, event.itemid, event.value, event.valueuom, {label}
            FROM procedureevents AS event
            {join}
            WHERE event.subject_id = ? AND (? IS NULL OR event.hadm_id = ?) AND (? IS NULL OR event.stay_id = ?)
              AND (? IS NULL OR COALESCE(event.starttime, event.storetime) >= ?)
              AND (? IS NULL OR COALESCE(event.starttime, event.storetime) <= ?)
            ORDER BY COALESCE(event.starttime, event.storetime) DESC,
                     event.subject_id DESC, event.hadm_id DESC, event.stay_id DESC,
                     event.itemid DESC, event.storetime DESC
            LIMIT ?
            """,
            self._hadm_stay_time_params(query),
        )
        return [
            self._record(
                "icu_procedure",
                {key: row[key] for key in ("itemid", "label", "starttime", "endtime", "storetime", "value", "valueuom")},
                row,
                module="icu",
                table="procedureevents",
                source_key=self._composite_key(
                    row, ("subject_id", "hadm_id", "stay_id", "event_time", "itemid", "storetime")
                ),
                related_sources=[self._dictionary_lineage(row, "icu", "d_items", f"itemid={row['itemid']}")]
                if dictionary_loaded
                else [],
            )
            for row in rows
        ]

    def _load_allow_listed_tables(self) -> set[str]:
        rows = self._execute("SELECT name FROM sqlite_master WHERE type = ?", ("table",))
        return {row["name"] for row in rows if row["name"] in ALLOWED_SOURCE_TABLES}

    def _load_table_columns(self) -> dict[str, set[str]]:
        return {
            table: {row["name"] for row in self._connection.execute(f"PRAGMA table_info({table})")}
            for table in self._tables
        }

    def _exists(self, sql: str, params: tuple[Any, ...]) -> bool:
        return bool(self._execute(sql, params))

    def _execute(self, sql: str, params: tuple[Any, ...]) -> list[sqlite3.Row]:
        deadline = time.monotonic() + self._query_timeout_seconds

        def abort_if_timed_out() -> int:
            return int(time.monotonic() >= deadline)

        self._connection.set_progress_handler(abort_if_timed_out, 1_000)
        try:
            return list(self._connection.execute(sql, params))
        except sqlite3.OperationalError as error:
            if time.monotonic() >= deadline:
                raise ClinicalQueryTimeout from error
            raise
        finally:
            self._connection.set_progress_handler(None, 0)

    def _record(
        self,
        record_type: str,
        data: dict[str, Any],
        row: sqlite3.Row,
        *,
        module: str,
        table: str,
        source_key: str,
        related_sources: list[SourceLineage] | None = None,
    ) -> EvidenceRecord:
        return EvidenceRecord(
            record_type=record_type,
            data=data,
            lineage=SourceLineage(
                dataset=self._source_dataset,
                version=self._source_version,
                module=module,
                table=table,
                source_row_key=source_key,
                subject_id=row["subject_id"],
                hadm_id=row["hadm_id"] if "hadm_id" in row.keys() else None,
                stay_id=row["stay_id"] if "stay_id" in row.keys() else None,
                event_time=self._event_time(row["event_time"]) if "event_time" in row.keys() else None,
            ),
            related_sources=related_sources or [],
        )

    def _dictionary_lineage(
        self, row: sqlite3.Row, module: str, table: str, source_key: str
    ) -> SourceLineage:
        return SourceLineage(
            dataset=self._source_dataset,
            version=self._source_version,
            module=module,
            table=table,
            source_row_key=source_key,
            subject_id=row["subject_id"],
            hadm_id=row["hadm_id"] if "hadm_id" in row.keys() else None,
            stay_id=row["stay_id"] if "stay_id" in row.keys() else None,
            event_time=self._event_time(row["event_time"]) if "event_time" in row.keys() else None,
        )

    @staticmethod
    def _event_time(value: str | datetime | None) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value)

    @staticmethod
    def _composite_key(row: sqlite3.Row, columns: Iterable[str]) -> str:
        return "|".join("" if row[column] is None else str(row[column]) for column in columns)

    @staticmethod
    def _time_value(value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is not None and value.utcoffset() is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value.isoformat(sep=" ")

    def _hadm_time_params(self, query: ClinicalQuery) -> tuple[Any, ...]:
        from_time = self._time_value(query.from_time)
        to_time = self._time_value(query.to_time)
        return (
            query.subject_id,
            query.hadm_id,
            query.hadm_id,
            from_time,
            from_time,
            to_time,
            to_time,
            query.limit + 1,
        )

    def _hadm_stay_time_params(self, query: ClinicalQuery) -> tuple[Any, ...]:
        from_time = self._time_value(query.from_time)
        to_time = self._time_value(query.to_time)
        return (
            query.subject_id,
            query.hadm_id,
            query.hadm_id,
            query.stay_id,
            query.stay_id,
            from_time,
            from_time,
            to_time,
            to_time,
            query.limit + 1,
        )

    def _fetch(
        self,
        records: list[EvidenceRecord],
        unavailable: list[str],
        limit: int,
        cursor_position: CursorPosition | None = None,
    ) -> RepositoryFetch:
        records.sort(key=self._record_sort_key, reverse=True)
        if cursor_position is not None:
            cursor_key = self._position_sort_key(cursor_position)
            records = [record for record in records if self._record_sort_key(record) < cursor_key]

        has_more = len(records) > limit
        page_records = records[:limit]
        next_position = self._position_from_record(page_records[-1]) if has_more else None
        return RepositoryFetch(
            records=page_records,
            unavailable_sources=list(dict.fromkeys(unavailable)),
            next_position=next_position,
            has_more=has_more,
        )

    @classmethod
    def _record_sort_key(cls, record: EvidenceRecord) -> tuple[datetime, str, tuple[tuple[int, str], ...]]:
        event_time = cls._normalized_sort_time(record.lineage.event_time)
        return event_time, record.lineage.table, cls._natural_source_key(record.lineage.source_row_key)

    @classmethod
    def _position_sort_key(cls, position: CursorPosition) -> tuple[datetime, str, tuple[tuple[int, str], ...]]:
        return (
            cls._normalized_sort_time(position.event_time),
            position.domain,
            cls._natural_source_key(position.source_key),
        )

    @staticmethod
    def _normalized_sort_time(value: datetime | None) -> datetime:
        if value is None:
            return datetime.min
        if value.tzinfo is not None and value.utcoffset() is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    @staticmethod
    def _natural_source_key(value: str) -> tuple[tuple[int, str], ...]:
        parts: list[tuple[int, str]] = []
        for part in value.split("|"):
            prefix, separator, suffix = part.rpartition("=")
            if separator and suffix.isdigit():
                parts.append((1, f"{prefix}\x00{int(suffix):020d}"))
            else:
                parts.append((0, part))
        return tuple(parts)

    @staticmethod
    def _position_from_record(record: EvidenceRecord) -> CursorPosition:
        event_time = record.lineage.event_time
        if event_time is not None and (event_time.tzinfo is None or event_time.utcoffset() is None):
            event_time = event_time.replace(tzinfo=UTC)
        return CursorPosition(
            event_time=event_time,
            domain=record.lineage.table,
            source_key=record.lineage.source_row_key,
        )
