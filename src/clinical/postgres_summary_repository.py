"""Durable, writable application storage for clinical summary review versions using PostgreSQL."""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from src.clinical.audit import AuditEvent, AuditSink
from src.clinical.errors import ReviewPolicyError
from src.clinical.summary_schemas import ClinicalSummaryDraft
from src.clinical.summary_repository import SummaryStatus, SummaryVersion, _TRANSITIONS


class PostgresSummaryRepository(AuditSink):
    """Owns the writable application database in PostgreSQL."""

    def __init__(self, dsn: str, pool_size: int = 5) -> None:
        if not dsn:
            raise RuntimeError("PostgreSQL DSN is required")
        
        try:
            # pyrefly: ignore [missing-import]
            from psycopg.rows import dict_row
            # pyrefly: ignore [missing-import]
            from psycopg_pool import ConnectionPool
        except ImportError as error:
            raise RuntimeError("psycopg and psycopg_pool must be installed") from error

        self._pool = ConnectionPool(
            conninfo=dsn,
            min_size=1,
            max_size=pool_size,
            kwargs={"autocommit": True, "row_factory": dict_row},
            open=False,
        )
        self._pool.open(wait=True)
        self._initialize()

    def close(self) -> None:
        if getattr(self, "_pool", None) is not None:
            self._pool.close()

    def create_draft(self, draft: ClinicalSummaryDraft, actor_id: str) -> SummaryVersion:
        if draft.status != "DRAFT":
            raise ReviewPolicyError("Only draft summaries can be created.")
        version = self._new_version(draft, 1, "DRAFT", actor_id, None)
        
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                # In PostgreSQL, we can use an explicit transaction block
                cursor.execute("BEGIN")
                try:
                    existing = self._summary_in_connection(cursor, draft.summary_id)
                    if existing is not None:
                        if (existing.draft.subject_id, existing.draft.hadm_id, existing.draft.stay_id) != (
                            draft.subject_id, draft.hadm_id, draft.stay_id,
                        ):
                            raise ReviewPolicyError("Summary identifier is already bound to another clinical scope.")
                        self._record(cursor, self._scope_event(draft, actor_id, "GENERATE_CLINICAL_SUMMARY", "SUCCESS"))
                        connection.commit()
                        return existing
                        
                    cursor.execute(
                        """INSERT INTO summaries (summary_id, subject_id, hadm_id, stay_id, current_version_id)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (str(version.summary_id), draft.subject_id, draft.hadm_id, draft.stay_id, str(version.version_id)),
                    )
                    self._store_version(cursor, version)
                    self._record(cursor, self._scope_event(draft, actor_id, "GENERATE_CLINICAL_SUMMARY", "SUCCESS"))
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
        return version

    def get(self, summary_id: UUID) -> SummaryVersion:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT version_id, summary_id, version_number, status, actor_id, reason, created_at, draft_json
                       FROM summary_versions WHERE summary_id = %s ORDER BY version_number DESC LIMIT 1""",
                    (str(summary_id),),
                )
                row = cursor.fetchone()
        if row is None:
            raise ReviewPolicyError("Summary review policy cannot be satisfied.")
        return self._version_from_row(row)

    def get_for_subject(self, summary_id: UUID, subject_id: int) -> SummaryVersion | None:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT version_id, version.summary_id, version_number, status, actor_id, reason, created_at, draft_json
                       FROM summary_versions AS version
                       JOIN summaries AS summary ON summary.summary_id = version.summary_id
                       WHERE version.summary_id = %s AND summary.subject_id = %s
                       ORDER BY version_number DESC LIMIT 1""",
                    (str(summary_id), subject_id),
                )
                row = cursor.fetchone()
        return self._version_from_row(row) if row is not None else None

    def get_latest_for_subject(self, subject_id: int) -> SummaryVersion | None:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT version_id, version.summary_id, version_number, status, actor_id, reason, created_at, draft_json
                       FROM summary_versions AS version
                       JOIN summaries AS summary ON summary.current_version_id = version.version_id
                       WHERE summary.subject_id = %s
                       ORDER BY version.created_at DESC LIMIT 1""",
                    (subject_id,),
                )
                row = cursor.fetchone()
        return self._version_from_row(row) if row is not None else None

    def update_draft(
        self, summary_id: UUID, actor_id: str, patch: ClinicalSummaryDraft, reason: str | None, event: AuditEvent
    ) -> SummaryVersion:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("BEGIN")
                try:
                    current = self._current_version(cursor, summary_id)
                    if current.status not in {"DRAFT", "NEEDS_REVISION"}:
                        raise ReviewPolicyError("Only a current draft or revision may be edited.")
                    if patch.summary_id != summary_id or (patch.subject_id, patch.hadm_id, patch.stay_id) != (
                        current.draft.subject_id, current.draft.hadm_id, current.draft.stay_id,
                    ):
                        raise ReviewPolicyError("Edited summary identity and scope must remain unchanged.")
                    if event.user_id != actor_id or (event.subject_id, event.hadm_id, event.stay_id) != (
                        current.draft.subject_id, current.draft.hadm_id, current.draft.stay_id,
                    ):
                        raise ReviewPolicyError("Edited summary audit scope must match the persisted summary.")
                    
                    draft = patch.model_copy(
                        update={
                            "summary_id": summary_id,
                            "subject_id": current.draft.subject_id,
                            "hadm_id": current.draft.hadm_id,
                            "stay_id": current.draft.stay_id,
                            "status": "NEEDS_REVISION",
                            "trace_id": event.trace_id,
                        }
                    )
                    version = self._new_version(draft, current.version_number + 1, "NEEDS_REVISION", actor_id, reason)
                    self._store_version(cursor, version)
                    cursor.execute(
                        "UPDATE summaries SET current_version_id = %s WHERE summary_id = %s",
                        (str(version.version_id), str(summary_id)),
                    )
                    self._record(cursor, event)
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
        return version

    def list_versions(self, summary_id: UUID) -> list[SummaryVersion]:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT version_id, summary_id, version_number, status, actor_id, reason, created_at, draft_json
                       FROM summary_versions WHERE summary_id = %s ORDER BY version_number""",
                    (str(summary_id),),
                )
                rows = cursor.fetchall()
        return [self._version_from_row(row) for row in rows]

    def transition(
        self, summary_id: UUID, status: str, actor_id: str, reason: str | None, event: AuditEvent
    ) -> SummaryVersion:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("BEGIN")
                try:
                    current = self._current_version(cursor, summary_id)
                    if status not in _TRANSITIONS.get(current.status, set()):
                        raise ReviewPolicyError("Summary state transition is not permitted.")
                    self._validate_transition_event(current, actor_id, status, event)
                    draft = current.draft.model_copy(update={"status": status, "trace_id": event.trace_id})
                    version = self._new_version(draft, current.version_number + 1, status, actor_id, reason)
                    self._store_version(cursor, version)
                    cursor.execute(
                        "UPDATE summaries SET current_version_id = %s WHERE summary_id = %s",
                        (str(version.version_id), str(summary_id)),
                    )
                    self._record(cursor, event)
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
        return version

    def save_checklist(self, version_id: UUID, values: tuple[bool, bool, bool, bool]) -> None:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO review_checklists (
                        version_id, reviewed_summary, checked_critical_evidence,
                        understands_ai_limitations, confirms_edits
                    ) VALUES (%s, %s, %s, %s, %s)""",
                    (str(version_id), *values),
                )

    def approve(
        self, summary_id: UUID, actor_id: str, checklist: tuple[bool, bool, bool, bool], event: AuditEvent,
    ) -> SummaryVersion:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("BEGIN")
                try:
                    current = self._current_version(cursor, summary_id)
                    if "APPROVED" not in _TRANSITIONS.get(current.status, set()):
                        raise ReviewPolicyError("Summary state transition is not permitted.")
                    self._validate_transition_event(current, actor_id, "APPROVED", event)
                    draft = current.draft.model_copy(update={"status": "APPROVED", "trace_id": event.trace_id})
                    version = self._new_version(draft, current.version_number + 1, "APPROVED", actor_id, None)
                    self._store_version(cursor, version)
                    cursor.execute(
                        "UPDATE summaries SET current_version_id = %s WHERE summary_id = %s",
                        (str(version.version_id), str(summary_id)),
                    )
                    self._save_checklist(cursor, version.version_id, checklist)
                    self._record(cursor, event)
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
        return version

    def confirm_conflict(
        self, summary_id: UUID, actor_id: str, conflict_id: str, resolution_note: str, event: AuditEvent
    ) -> SummaryVersion:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("BEGIN")
                try:
                    current = self._current_version(cursor, summary_id)
                    if current.status not in {"DRAFT", "NEEDS_REVISION"}:
                        raise ReviewPolicyError("Only a current draft or revision may be edited.")
                    found = False
                    conflicts = []
                    for conflict in current.draft.conflicts:
                        if conflict.conflict_id == conflict_id:
                            found = True
                            conflicts.append(
                                conflict.model_copy(
                                    update={
                                        "status": "RESOLVED",
                                        "resolved_by": actor_id,
                                        "resolution_note": resolution_note,
                                    }
                                )
                            )
                        else:
                            conflicts.append(conflict)
                    if not found:
                        raise ReviewPolicyError("Conflict resolution is not permitted.")
                    draft = current.draft.model_copy(update={"conflicts": conflicts, "status": "NEEDS_REVISION"})
                    version = self._new_version(
                        draft, current.version_number + 1, "NEEDS_REVISION", actor_id, "Doctor confirmed conflict resolution"
                    )
                    self._store_version(cursor, version)
                    cursor.execute(
                        "UPDATE summaries SET current_version_id = %s WHERE summary_id = %s",
                        (str(version.version_id), str(summary_id)),
                    )
                    cursor.execute(
                        """INSERT INTO conflict_resolutions (version_id, conflict_id, resolver_id, resolution_note, resolved_at)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (str(version.version_id), conflict_id, actor_id, resolution_note, datetime.now(UTC).isoformat()),
                    )
                    self._record(cursor, event)
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
        return version

    def confirmed_conflicts(self, version_id: UUID) -> set[tuple[str, str, str]]:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT conflict_id, resolver_id, resolution_note FROM conflict_resolutions WHERE version_id = %s",
                    (str(version_id),),
                )
                rows = cursor.fetchall()
        return {(row["conflict_id"], row["resolver_id"], row["resolution_note"]) for row in rows}

    def record(self, event: AuditEvent) -> None:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                self._record(cursor, event)

    def _initialize(self) -> None:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
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
                        version_id TEXT PRIMARY KEY, reviewed_summary BOOLEAN NOT NULL,
                        checked_critical_evidence BOOLEAN NOT NULL, understands_ai_limitations BOOLEAN NOT NULL,
                        confirms_edits BOOLEAN NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS conflict_resolutions (
                        version_id TEXT NOT NULL, conflict_id TEXT NOT NULL, resolver_id TEXT NOT NULL,
                        resolution_note TEXT NOT NULL, resolved_at TEXT NOT NULL,
                        PRIMARY KEY (version_id, conflict_id)
                    );
                    CREATE TABLE IF NOT EXISTS audit_events (
                        user_id TEXT NOT NULL, action TEXT NOT NULL, subject_id INTEGER NOT NULL,
                        hadm_id INTEGER, stay_id INTEGER, result TEXT NOT NULL, trace_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL
                    );
                    """
                )

    def _store_version(self, cursor: Any, version: SummaryVersion) -> None:
        cursor.execute(
            """INSERT INTO summary_versions (
                version_id, summary_id, version_number, status, actor_id, reason, created_at, draft_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                str(version.version_id), str(version.summary_id), version.version_number, version.status,
                version.actor_id, version.reason, version.created_at.isoformat(), version.draft.model_dump_json(),
            ),
        )
        
        claims = [
            (str(version.version_id), claim.claim_id, section, claim.model_dump_json())
            for section, section_claims in version.draft.sections.items()
            for claim in section_claims
        ]
        if claims:
            cursor.executemany(
                "INSERT INTO summary_claims (version_id, claim_id, section, claim_json) VALUES (%s, %s, %s, %s)",
                claims,
            )

        citations = [
            (str(version.version_id), citation.citation_id, citation.model_dump_json())
            for citation in version.draft.citations
        ]
        if citations:
            cursor.executemany(
                "INSERT INTO summary_citations (version_id, citation_id, citation_json) VALUES (%s, %s, %s)",
                citations,
            )

        conflicts = [
            (str(version.version_id), conflict.conflict_id, conflict.model_dump_json())
            for conflict in version.draft.conflicts
        ]
        if conflicts:
            cursor.executemany(
                "INSERT INTO summary_conflicts (version_id, conflict_id, conflict_json) VALUES (%s, %s, %s)",
                conflicts,
            )

    @staticmethod
    def _save_checklist(
        cursor: Any, version_id: UUID, values: tuple[bool, bool, bool, bool]
    ) -> None:
        cursor.execute(
            """INSERT INTO review_checklists (
                version_id, reviewed_summary, checked_critical_evidence,
                understands_ai_limitations, confirms_edits
            ) VALUES (%s, %s, %s, %s, %s)""",
            (str(version_id), *values),
        )

    @staticmethod
    def _record(cursor: Any, event: AuditEvent) -> None:
        cursor.execute(
            """INSERT INTO audit_events (
                user_id, action, subject_id, hadm_id, stay_id, result, trace_id, timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                event.user_id, event.action, event.subject_id, event.hadm_id, event.stay_id,
                event.result, event.trace_id, event.timestamp.isoformat(),
            ),
        )

    def _current_version(self, cursor: Any, summary_id: UUID) -> SummaryVersion:
        cursor.execute(
            """SELECT version_id, summary_id, version_number, status, actor_id, reason, created_at, draft_json
               FROM summary_versions WHERE summary_id = %s ORDER BY version_number DESC LIMIT 1""",
            (str(summary_id),),
        )
        row = cursor.fetchone()
        if row is None:
            raise ReviewPolicyError("Summary review policy cannot be satisfied.")
        return self._version_from_row(row)

    def _summary_in_connection(self, cursor: Any, summary_id: UUID) -> SummaryVersion | None:
        cursor.execute(
            """SELECT version_id, summary_id, version_number, status, actor_id, reason, created_at, draft_json
               FROM summary_versions WHERE summary_id = %s ORDER BY version_number DESC LIMIT 1""",
            (str(summary_id),),
        )
        row = cursor.fetchone()
        return self._version_from_row(row) if row is not None else None

    @staticmethod
    def _validate_transition_event(
        current: SummaryVersion, actor_id: str, status: str, event: AuditEvent
    ) -> None:
        action_by_status = {
            "REJECTED": "REJECT_CLINICAL_SUMMARY",
            "APPROVED": "APPROVE_CLINICAL_SUMMARY",
            "EXPORTED": "EXPORT_CLINICAL_SUMMARY",
        }
        if (
            event.user_id != actor_id
            or event.action != action_by_status.get(status)
            or event.result != "SUCCESS"
            or (event.subject_id, event.hadm_id, event.stay_id)
            != (current.draft.subject_id, current.draft.hadm_id, current.draft.stay_id)
        ):
            raise ReviewPolicyError("Summary transition audit scope must match the persisted summary.")

    @staticmethod
    def _new_version(
        draft: ClinicalSummaryDraft, number: int, status: SummaryStatus, actor_id: str, reason: str | None
    ) -> SummaryVersion:
        return SummaryVersion(
            version_id=uuid4(), summary_id=draft.summary_id, version_number=number, status=status,
            actor_id=actor_id, reason=reason, created_at=datetime.now(UTC), draft=draft,
        )

    @staticmethod
    def _version_from_row(row: dict[str, Any]) -> SummaryVersion:
        draft_json_str = row["draft_json"] if isinstance(row["draft_json"], str) else json.dumps(row["draft_json"])
        return SummaryVersion(
            version_id=UUID(row["version_id"]), summary_id=UUID(row["summary_id"]),
            version_number=row["version_number"], status=row["status"], actor_id=row["actor_id"],
            reason=row["reason"], created_at=datetime.fromisoformat(row["created_at"]),
            draft=ClinicalSummaryDraft.model_validate(json.loads(draft_json_str)),
        )

    @staticmethod
    def _scope_event(draft: ClinicalSummaryDraft, actor_id: str, action: str, result: str) -> AuditEvent:
        return AuditEvent(
            user_id=actor_id,
            action=action,
            subject_id=draft.subject_id,
            hadm_id=draft.hadm_id,
            stay_id=draft.stay_id,
            result=result,
            trace_id=draft.trace_id,
            timestamp=datetime.now(UTC),
        )
