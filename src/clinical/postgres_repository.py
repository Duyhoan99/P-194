"""PostgreSQL production adapter using the shared allow-listed repository queries."""

from datetime import UTC, datetime
from typing import Any

from src.clinical.errors import ClinicalDatabaseUnavailable, ClinicalQueryTimeout
from src.clinical.repository import ALLOWED_SOURCE_TABLES, SQLiteClinicalRepository


class PostgresClinicalRepository(SQLiteClinicalRepository):
    """Read-only PostgreSQL adapter with bounded pooled connections and timeouts."""

    def __init__(
        self,
        dsn: str,
        query_timeout_seconds: float = 2.0,
        pool_size: int = 5,
        source_dataset: str = "MIMIC-IV",
        source_version: str = "3.1",
    ) -> None:
        if not dsn:
            raise ClinicalDatabaseUnavailable
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as error:
            raise ClinicalDatabaseUnavailable from error

        self._query_timeout_seconds = query_timeout_seconds
        self._source_dataset = source_dataset
        self._source_version = source_version
        try:
            self._pool = ConnectionPool(
                conninfo=dsn,
                min_size=1,
                max_size=pool_size,
                kwargs={"autocommit": True, "row_factory": dict_row},
                open=False,
            )
            self._pool.open(wait=True)
            self._tables = self._load_allow_listed_tables()
        except Exception as error:
            self.close()
            raise ClinicalDatabaseUnavailable from error

    def close(self) -> None:
        pool = getattr(self, "_pool", None)
        if pool is not None:
            pool.close()

    def _load_allow_listed_tables(self) -> set[str]:
        rows = self._execute(
            """
            SELECT table_name AS name
            FROM information_schema.tables
            WHERE table_schema = current_schema()
            """,
            (),
        )
        return {row["name"] for row in rows if row["name"] in ALLOWED_SOURCE_TABLES}

    def _execute(self, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        postgres_sql = sql.replace("?", "%s")
        try:
            with self._pool.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET default_transaction_read_only = on")
                    cursor.execute("SET statement_timeout = %s", (int(self._query_timeout_seconds * 1000),))
                    cursor.execute(postgres_sql, params)
                    return list(cursor.fetchall())
        except Exception as error:
            if getattr(error, "sqlstate", None) == "57014":
                raise ClinicalQueryTimeout from error
            raise ClinicalDatabaseUnavailable from error

    @staticmethod
    def _time_value(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None and value.utcoffset() is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value
