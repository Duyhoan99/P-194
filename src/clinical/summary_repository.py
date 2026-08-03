"""Durable, writable application storage for clinical summary review versions."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel

from src.clinical.audit import AuditEvent, AuditSink
from src.clinical.errors import ReviewPolicyError
from src.clinical.summary_schemas import ClinicalSummaryDraft
from src.config import get_settings

SummaryStatus = Literal["DRAFT", "NEEDS_REVISION", "REJECTED", "APPROVED", "EXPORTED"]
_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"NEEDS_REVISION", "REJECTED", "APPROVED"},
    "APPROVED": {"EXPORTED"},
}


class SummaryVersion(BaseModel):
    version_id: UUID
    summary_id: UUID
    version_number: int
    status: SummaryStatus
    actor_id: str
    reason: str | None
    created_at: datetime
    draft: ClinicalSummaryDraft


class SummaryRepository(Protocol):
    def create_draft(self, draft: ClinicalSummaryDraft, actor_id: str) -> SummaryVersion: ...

    def get(self, summary_id: UUID) -> SummaryVersion: ...

    def get_for_subject(self, summary_id: UUID, subject_id: int) -> SummaryVersion | None: ...

    def update_draft(
        self, summary_id: UUID, actor_id: str, patch: ClinicalSummaryDraft, reason: str | None
    ) -> SummaryVersion: ...

    def list_versions(self, summary_id: UUID) -> list[SummaryVersion]: ...

    def transition(
        self, summary_id: UUID, status: str, actor_id: str, reason: str | None
    ) -> SummaryVersion: ...


class SQLiteSummaryRepository(AuditSink):
    """Owns the writable application database, never the clinical source database."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(Path(db_path))
        if Path(self.db_path).resolve() == Path(get_settings().clinical_database_path).resolve():
            raise ValueError("summary application database must differ from the clinical source database")
        self._initialize()

    def create_draft(self, draft: ClinicalSummaryDraft, actor_id: str) -> SummaryVersion:
        if draft.status != "DRAFT":
            raise ReviewPolicyError("Only draft summaries can be created.")
        version = self._new_version(draft, 1, "DRAFT", actor_id, None)
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO summaries (summary_id, subject_id, hadm_id, stay_id, current_version_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(version.summary_id), draft.subject_id, draft.hadm_id, draft.stay_id, str(version.version_id)),
            )
            self._store_version(connection, version)
        self._record_scope_event(version, "GENERATE_CLINICAL_SUMMARY", "SUCCESS")
        return version

    def get(self, summary_id: UUID) -> SummaryVersion:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT version_id, summary_id, version_number, status, actor_id, reason, created_at, draft_json
                   FROM summary_versions WHERE summary_id = ? ORDER BY version_number DESC LIMIT 1""",
                (str(summary_id),),
            ).fetchone()
        if row is None:
            raise ReviewPolicyError("Summary review policy cannot be satisfied.")
        return self._version_from_row(row)

    def get_for_subject(self, summary_id: UUID, subject_id: int) -> SummaryVersion | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT version_id, version.summary_id, version_number, status, actor_id, reason, created_at, draft_json
                   FROM summary_versions AS version
                   JOIN summaries AS summary ON summary.summary_id = version.summary_id
                   WHERE version.summary_id = ? AND summary.subject_id = ?
                   ORDER BY version_number DESC LIMIT 1""",
                (str(summary_id), subject_id),
            ).fetchone()
        return self._version_from_row(row) if row is not None else None

    def update_draft(
        self, summary_id: UUID, actor_id: str, patch: ClinicalSummaryDraft, reason: str | None
    ) -> SummaryVersion:
        current = self.get(summary_id)
        if current.status != "DRAFT":
            raise ReviewPolicyError("Only the current draft may be edited.")
        draft = patch.model_copy(update={"summary_id": summary_id, "status": "NEEDS_REVISION"})
        version = self._new_version(draft, current.version_number + 1, "NEEDS_REVISION", actor_id, reason)
        with self._connection() as connection:
            self._store_version(connection, version)
            connection.execute(
                "UPDATE summaries SET current_version_id = ? WHERE summary_id = ?",
                (str(version.version_id), str(summary_id)),
            )
        self._record_scope_event(version, "EDIT_CLINICAL_SUMMARY", "SUCCESS")
        return version

    def list_versions(self, summary_id: UUID) -> list[SummaryVersion]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT version_id, summary_id, version_number, status, actor_id, reason, created_at, draft_json
                   FROM summary_versions WHERE summary_id = ? ORDER BY version_number""",
                (str(summary_id),),
            ).fetchall()
        return [self._version_from_row(row) for row in rows]

    def transition(
        self, summary_id: UUID, status: str, actor_id: str, reason: str | None
    ) -> SummaryVersion:
        current = self.get(summary_id)
        if status not in _TRANSITIONS.get(current.status, set()):
            raise ReviewPolicyError("Summary state transition is not permitted.")
        draft = current.draft.model_copy(update={"status": status})
        version = self._new_version(draft, current.version_number + 1, status, actor_id, reason)
        with self._connection() as connection:
            self._store_version(connection, version)
            connection.execute(
                "UPDATE summaries SET current_version_id = ? WHERE summary_id = ?",
                (str(version.version_id), str(summary_id)),
            )
        return version

    def save_checklist(self, version_id: UUID, values: tuple[bool, bool, bool, bool]) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO review_checklists (
                    version_id, reviewed_summary, checked_critical_evidence,
                    understands_ai_limitations, confirms_edits
                ) VALUES (?, ?, ?, ?, ?)""",
                (str(version_id), *values),
            )

    def record(self, event: AuditEvent) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO audit_events (
                    user_id, action, subject_id, hadm_id, stay_id, result, trace_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.user_id,
                    event.action,
                    event.subject_id,
                    event.hadm_id,
                    event.stay_id,
                    event.result,
                    event.trace_id,
                    event.timestamp.isoformat(),
                ),
            )

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS summaries (
                    summary_id TEXT PRIMARY KEY, subject_id INTEGER NOT NULL, hadm_id INTEGER,
                    stay_id INTEGER, current_version_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS summary_versions (
                    version_id TEXT PRIMARY KEY, summary_id TEXT NOT NULL, version_number INTEGER NOT NULL,
                    status TEXT NOT NULL, actor_id TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL,
                    draft_json TEXT NOT NULL, UNIQUE(summary_id, version_number)
                );
                CREATE TABLE IF NOT EXISTS summary_claims (
                    version_id TEXT NOT NULL, claim_id TEXT NOT NULL, section TEXT NOT NULL,
                    claim_json TEXT NOT NULL, PRIMARY KEY (version_id, claim_id)
                );
                CREATE TABLE IF NOT EXISTS summary_citations (
                    version_id TEXT NOT NULL, citation_id TEXT NOT NULL, citation_json TEXT NOT NULL,
                    PRIMARY KEY (version_id, citation_id)
                );
                CREATE TABLE IF NOT EXISTS summary_conflicts (
                    version_id TEXT NOT NULL, conflict_id TEXT NOT NULL, conflict_json TEXT NOT NULL,
                    PRIMARY KEY (version_id, conflict_id)
                );
                CREATE TABLE IF NOT EXISTS review_checklists (
                    version_id TEXT PRIMARY KEY, reviewed_summary INTEGER NOT NULL,
                    checked_critical_evidence INTEGER NOT NULL, understands_ai_limitations INTEGER NOT NULL,
                    confirms_edits INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    user_id TEXT NOT NULL, action TEXT NOT NULL, subject_id INTEGER NOT NULL,
                    hadm_id INTEGER, stay_id INTEGER, result TEXT NOT NULL, trace_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                );
                """
            )

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _store_version(self, connection: sqlite3.Connection, version: SummaryVersion) -> None:
        connection.execute(
            """INSERT INTO summary_versions (
                version_id, summary_id, version_number, status, actor_id, reason, created_at, draft_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(version.version_id), str(version.summary_id), version.version_number, version.status,
                version.actor_id, version.reason, version.created_at.isoformat(), version.draft.model_dump_json(),
            ),
        )
        connection.executemany(
            "INSERT INTO summary_claims (version_id, claim_id, section, claim_json) VALUES (?, ?, ?, ?)",
            [
                (str(version.version_id), claim.claim_id, section, claim.model_dump_json())
                for section, claims in version.draft.sections.items()
                for claim in claims
            ],
        )
        connection.executemany(
            "INSERT INTO summary_citations (version_id, citation_id, citation_json) VALUES (?, ?, ?)",
            [(str(version.version_id), citation.citation_id, citation.model_dump_json()) for citation in version.draft.citations],
        )
        connection.executemany(
            "INSERT INTO summary_conflicts (version_id, conflict_id, conflict_json) VALUES (?, ?, ?)",
            [(str(version.version_id), conflict.conflict_id, conflict.model_dump_json()) for conflict in version.draft.conflicts],
        )

    @staticmethod
    def _new_version(
        draft: ClinicalSummaryDraft, number: int, status: SummaryStatus, actor_id: str, reason: str | None
    ) -> SummaryVersion:
        return SummaryVersion(
            version_id=uuid4(), summary_id=draft.summary_id, version_number=number, status=status,
            actor_id=actor_id, reason=reason, created_at=datetime.now(UTC), draft=draft,
        )

    @staticmethod
    def _version_from_row(row: sqlite3.Row) -> SummaryVersion:
        return SummaryVersion(
            version_id=UUID(row["version_id"]), summary_id=UUID(row["summary_id"]),
            version_number=row["version_number"], status=row["status"], actor_id=row["actor_id"],
            reason=row["reason"], created_at=datetime.fromisoformat(row["created_at"]),
            draft=ClinicalSummaryDraft.model_validate(json.loads(row["draft_json"])),
        )

    def _record_scope_event(self, version: SummaryVersion, action: str, result: str) -> None:
        self.record(
            AuditEvent(
                user_id=version.actor_id, action=action, subject_id=version.draft.subject_id,
                hadm_id=version.draft.hadm_id, stay_id=version.draft.stay_id, result=result,
                trace_id=version.draft.trace_id, timestamp=version.created_at,
            )
        )
