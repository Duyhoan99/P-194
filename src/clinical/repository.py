"""Read-only, allow-listed SQLite retrieval for clinical source records."""

import sqlite3
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from src.clinical.availability import ALLOWED_SOURCE_TABLES, SourceAvailability, source_availability
from src.clinical.errors import ClinicalQueryTimeout
from src.clinical.schemas import ClinicalQuery, EvidenceRecord, SourceLineage


class RepositoryFetch:
    """Records returned by one repository domain plus unavailable source tables."""

    def __init__(self, records: list[EvidenceRecord], unavailable_sources: list[str]) -> None:
        self.records = records
        self.unavailable_sources = unavailable_sources


class ClinicalRepository(Protocol):
    """Data access boundary used by the clinical retrieval service."""

    def validate_scope(self, query: ClinicalQuery) -> bool: ...

    def available_sources(self) -> SourceAvailability: ...

    def fetch_patient_overview(self, query: ClinicalQuery) -> RepositoryFetch: ...

    def fetch_encounter_timeline(self, query: ClinicalQuery) -> RepositoryFetch: ...

    def fetch_diagnoses_and_procedures(self, query: ClinicalQuery) -> RepositoryFetch: ...

    def fetch_laboratory_results(self, query: ClinicalQuery) -> RepositoryFetch: ...

    def fetch_microbiology_results(self, query: ClinicalQuery) -> RepositoryFetch: ...

    def fetch_icu_events(self, query: ClinicalQuery) -> RepositoryFetch: ...


class SQLiteClinicalRepository:
    """Clinical repository backed by a SQLite database opened in read-only mode."""

    def __init__(self, db_path: str, query_timeout_seconds: float = 2.0) -> None:
        self._query_timeout_seconds = query_timeout_seconds
        database_uri = f"{Path(db_path).resolve().as_uri()}?mode=ro"
        self._connection = sqlite3.connect(database_uri, uri=True, timeout=query_timeout_seconds)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA query_only = ON")
        self._tables = self._load_allow_listed_tables()

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

    def fetch_patient_overview(self, query: ClinicalQuery) -> RepositoryFetch:
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
                ORDER BY subject_id
                LIMIT ?
                """,
                (query.subject_id, query.limit),
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
        return self._fetch(records, unavailable, query.limit)

    def fetch_encounter_timeline(self, query: ClinicalQuery) -> RepositoryFetch:
        unavailable: list[str] = []
        records = self._admission_records(query, unavailable)
        records.extend(self._timeline_records(query, unavailable))
        return self._fetch(records, unavailable, query.limit)

    def fetch_diagnoses_and_procedures(self, query: ClinicalQuery) -> RepositoryFetch:
        records: list[EvidenceRecord] = []
        unavailable: list[str] = []
        records.extend(self._diagnosis_records(query, unavailable))
        records.extend(self._procedure_records(query, unavailable))
        records.extend(self._hcpcs_records(query, unavailable))
        records.extend(self._procedure_event_records(query, unavailable))
        return self._fetch(records, unavailable, query.limit)

    def fetch_laboratory_results(self, query: ClinicalQuery) -> RepositoryFetch:
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
                   event.charttime, event.charttime AS event_time, event.storetime, event.value, event.valuenum,
                   event.valueuom, event.ref_range_lower, event.ref_range_upper, event.flag,
                   {dictionary_columns}
                   event.labevent_id AS source_key
            FROM labevents AS event
            {dictionary_join}
            WHERE event.subject_id = ?
              AND (? IS NULL OR event.hadm_id = ?)
              AND (? IS NULL OR event.charttime >= ?)
              AND (? IS NULL OR event.charttime <= ?)
            ORDER BY event.charttime, event.labevent_id
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
        return self._fetch(records, unavailable, query.limit)

    def fetch_microbiology_results(self, query: ClinicalQuery) -> RepositoryFetch:
        if "microbiologyevents" not in self._tables:
            return RepositoryFetch(records=[], unavailable_sources=["microbiologyevents"])
        rows = self._execute(
            """
            SELECT microevent_id, subject_id, hadm_id, micro_specimen_id, chartdate, charttime,
                   charttime AS event_time, storedate, storetime, spec_type_desc, test_name, org_name, isolation, quantity, ab_name,
                   dilution_text, dilution_comparison, dilution_value, interpretation
            FROM microbiologyevents
            WHERE subject_id = ?
              AND (? IS NULL OR hadm_id = ?)
              AND (? IS NULL OR charttime >= ?)
              AND (? IS NULL OR charttime <= ?)
            ORDER BY charttime, micro_specimen_id, test_name, org_name, microevent_id
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
        return self._fetch(records, [], query.limit)

    def fetch_icu_events(self, query: ClinicalQuery) -> RepositoryFetch:
        unavailable: list[str] = []
        records: list[EvidenceRecord] = []
        records.extend(self._icu_stay_records(query, unavailable))
        records.extend(self._chart_event_records(query, unavailable))
        records.extend(self._datetime_event_records(query, unavailable))
        records.extend(self._input_event_records(query, unavailable))
        records.extend(self._output_event_records(query, unavailable))
        records.extend(self._procedure_event_records(query, unavailable))
        return self._fetch(records, unavailable, query.limit)

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
            ORDER BY admittime, hadm_id
            LIMIT ?
            """,
            (query.subject_id, query.hadm_id, query.hadm_id, query.limit),
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
                ORDER BY intime, transfer_id
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
                ORDER BY transfertime, hadm_id, curr_service
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
            ORDER BY event.hadm_id, event.seq_num, event.icd_code, event.icd_version
            LIMIT ?
            """,
            (query.subject_id, query.hadm_id, query.hadm_id, query.limit),
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
            ORDER BY event.chartdate, event.hadm_id, event.seq_num, event.icd_code
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
            ORDER BY event.chartdate, event.hadm_id, event.seq_num, event.hcpcs_cd
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
            ORDER BY intime, stay_id
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
            SELECT event.subject_id, event.hadm_id, event.stay_id, event.charttime, event.charttime AS event_time,
                   event.storetime, event.itemid, {selected_values}, {label}
            FROM {table} AS event
            {join}
            WHERE event.subject_id = ? AND (? IS NULL OR event.hadm_id = ?) AND (? IS NULL OR event.stay_id = ?)
              AND (? IS NULL OR event.charttime >= ?) AND (? IS NULL OR event.charttime <= ?)
            ORDER BY event.charttime, event.subject_id, event.hadm_id, event.stay_id, event.itemid, event.storetime
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
                    row, ("subject_id", "hadm_id", "stay_id", "event_time", "itemid", "storetime")
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
            SELECT event.subject_id, event.hadm_id, event.stay_id, event.starttime, event.starttime AS event_time,
                   event.endtime, event.storetime, event.itemid, event.amount, event.amountuom,
                   event.rate, event.rateuom, {label}
            FROM inputevents AS event
            {join}
            WHERE event.subject_id = ? AND (? IS NULL OR event.hadm_id = ?) AND (? IS NULL OR event.stay_id = ?)
              AND (? IS NULL OR event.starttime >= ?) AND (? IS NULL OR event.starttime <= ?)
            ORDER BY event.starttime, event.subject_id, event.hadm_id, event.stay_id, event.itemid, event.storetime
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
                    row, ("subject_id", "hadm_id", "stay_id", "event_time", "itemid", "storetime")
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
            SELECT event.subject_id, event.hadm_id, event.stay_id, event.starttime, event.starttime AS event_time,
                   event.endtime, event.storetime, event.itemid, event.value, event.valueuom, {label}
            FROM procedureevents AS event
            {join}
            WHERE event.subject_id = ? AND (? IS NULL OR event.hadm_id = ?) AND (? IS NULL OR event.stay_id = ?)
              AND (? IS NULL OR event.starttime >= ?) AND (? IS NULL OR event.starttime <= ?)
            ORDER BY event.starttime, event.subject_id, event.hadm_id, event.stay_id, event.itemid, event.storetime
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
                dataset="MIMIC-IV",
                version="3.1",
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
            dataset="MIMIC-IV",
            version="3.1",
            module=module,
            table=table,
            source_row_key=source_key,
            subject_id=row["subject_id"],
            hadm_id=row["hadm_id"] if "hadm_id" in row.keys() else None,
            stay_id=row["stay_id"] if "stay_id" in row.keys() else None,
            event_time=self._event_time(row["event_time"]) if "event_time" in row.keys() else None,
        )

    @staticmethod
    def _event_time(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value is not None else None

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
            query.limit,
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
            query.limit,
        )

    @staticmethod
    def _fetch(records: list[EvidenceRecord], unavailable: list[str], limit: int) -> RepositoryFetch:
        records.sort(
            key=lambda record: (
                record.lineage.event_time.isoformat() if record.lineage.event_time else "",
                record.lineage.source_row_key,
            )
        )
        return RepositoryFetch(records=records[:limit], unavailable_sources=list(dict.fromkeys(unavailable)))
