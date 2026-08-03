"""Read-only inspection of indexes and query plans for the SQLite clinical source."""

import argparse
import sqlite3
from pathlib import Path
from typing import Any

REQUIRED_INDEX_PREFIXES: dict[str, tuple[str, ...]] = {
    "patients": ("subject_id",),
    "admissions": ("subject_id", "hadm_id"),
    "icustays": ("subject_id", "hadm_id", "stay_id"),
    "labevents": ("subject_id", "hadm_id", "charttime", "labevent_id"),
    "chartevents": ("subject_id", "hadm_id", "stay_id", "charttime"),
}

QUERY_PLANS: dict[str, tuple[str, tuple[Any, ...]]] = {
    "patients": (
        "SELECT subject_id FROM patients WHERE subject_id = ? LIMIT ?",
        (1, 1),
    ),
    "admissions": (
        "SELECT hadm_id FROM admissions WHERE subject_id = ? AND hadm_id = ? LIMIT ?",
        (1, 1, 1),
    ),
    "icustays": (
        "SELECT stay_id FROM icustays WHERE subject_id = ? AND hadm_id = ? AND stay_id = ? LIMIT ?",
        (1, 1, 1, 1),
    ),
    "labevents": (
        "SELECT labevent_id FROM labevents WHERE subject_id = ? AND hadm_id = ? ORDER BY charttime DESC, labevent_id DESC LIMIT ?",
        (1, 1, 1),
    ),
    "chartevents": (
        "SELECT itemid FROM chartevents WHERE subject_id = ? AND hadm_id = ? AND stay_id = ? ORDER BY charttime DESC LIMIT ?",
        (1, 1, 1, 1),
    ),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    args = parser.parse_args(argv)
    database_uri = f"{args.database.resolve().as_uri()}?mode=ro"

    try:
        connection = sqlite3.connect(database_uri, uri=True)
    except sqlite3.Error:
        return 2

    missing = 0
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        for table, required_prefix in REQUIRED_INDEX_PREFIXES.items():
            if table not in tables:
                print(f"table={table} status=NOT_LOADED")
                continue
            indexes = _table_indexes(connection, table)
            matched = any(columns[: len(required_prefix)] == required_prefix for columns in indexes.values())
            status = "OK" if matched else "MISSING"
            print(f"table={table} status={status}")
            if not matched:
                missing += 1
            plan_sql, params = QUERY_PLANS[table]
            plan_rows = connection.execute(f"EXPLAIN QUERY PLAN {plan_sql}", params).fetchall()
            for plan_row in plan_rows:
                print(f"table={table} plan={plan_row[3]}")
    finally:
        connection.close()
    return 1 if missing else 0


def _table_indexes(connection: sqlite3.Connection, table: str) -> dict[str, tuple[str, ...]]:
    indexes: dict[str, tuple[str, ...]] = {}
    for index_row in connection.execute(f"PRAGMA index_list({_pragma_literal(table)})"):
        index_name = index_row[1]
        columns = tuple(
            row[2]
            for row in connection.execute(f"PRAGMA index_info({_pragma_literal(index_name)})")
        )
        indexes[index_name] = columns
    return indexes


def _pragma_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
