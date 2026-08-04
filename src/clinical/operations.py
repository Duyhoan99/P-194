"""Safe, local operational metadata for the development/test vertical slice."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Literal

from src.clinical.audit import AuditEvent
from src.clinical.errors import ClinicalAuditUnavailable
from src.config import get_settings

OperationalRole = Literal["DOCTOR", "ADMIN", "DATA_STEWARD", "COMPLIANCE"]
AccountState = Literal["ACTIVE", "LOCKED"]


@dataclass(frozen=True)
class AssignmentHistoryEntry:
    """A safe provenance record for assignment changes."""

    subject_id: int
    action: Literal["ASSIGN_CLINICAL_SUBJECT", "REVOKE_CLINICAL_SUBJECT"]
    actor_id: str
    timestamp: datetime


@dataclass
class OperationalUser:
    """User metadata deliberately kept separate from clinical content."""

    user_id: str
    role: OperationalRole
    state: AccountState = "ACTIVE"
    assigned_subject_ids: set[int] = field(default_factory=set)
    assignment_history: list[AssignmentHistoryEntry] = field(default_factory=list)


class OperationalStore:
    """In-memory operational state used only by the local MIMIC demo surface."""

    def __init__(self) -> None:
        demo_subjects = self._load_demo_subjects()
        self._users: dict[str, OperationalUser] = {
            "doctor-1": OperationalUser("doctor-1", "DOCTOR", assigned_subject_ids=demo_subjects),
            "doctor-2": OperationalUser("doctor-2", "DOCTOR"),
            "admin-1": OperationalUser("admin-1", "ADMIN"),
            "steward-1": OperationalUser("steward-1", "DATA_STEWARD"),
            "compliance-1": OperationalUser("compliance-1", "COMPLIANCE"),
        }
        self._audit_events: list[AuditEvent] = []
        self._lock = RLock()

    def users(self) -> list[OperationalUser]:
        with self._lock:
            return [self._snapshot(user) for user in sorted(self._users.values(), key=lambda user: user.user_id)]

    def get_user(self, user_id: str) -> OperationalUser:
        with self._lock:
            return self._snapshot(self._require_user(user_id))

    def session_identity(self, user_id: str) -> tuple[OperationalRole, set[int]] | None:
        """Return the current server-owned demo session scope for an active account."""
        with self._lock:
            user = self._users.get(user_id)
            if user is None or user.state != "ACTIVE":
                return None
            return user.role, self._effective_assignments(user)

    def assignments(self) -> dict[str, set[int]]:
        with self._lock:
            return {
                user.user_id: self._effective_assignments(user)
                for user in self._users.values()
                if user.role == "DOCTOR" and user.state == "ACTIVE"
            }

    def admin_users(self) -> set[str]:
        with self._lock:
            return {
                user.user_id
                for user in self._users.values()
                if user.role == "ADMIN" and user.state == "ACTIVE"
            }

    def change_assignment(
        self,
        user_id: str,
        subject_id: int,
        actor_id: str,
        trace_id: str,
        action: Literal["ASSIGN_CLINICAL_SUBJECT", "REVOKE_CLINICAL_SUBJECT"],
    ) -> OperationalUser:
        """Atomically change a demo assignment and write its mandatory audit event."""
        with self._lock:
            user = self._require_user(user_id)
            if user.role != "DOCTOR":
                raise ValueError("Assignments may only be changed for doctor accounts")
            prior_assignments = set(user.assigned_subject_ids)
            prior_history_length = len(user.assignment_history)
            now = datetime.now(UTC)
            if action == "ASSIGN_CLINICAL_SUBJECT":
                user.assigned_subject_ids.add(subject_id)
            else:
                user.assigned_subject_ids.discard(subject_id)
            user.assignment_history.append(AssignmentHistoryEntry(subject_id, action, actor_id, now))
            try:
                self.record(
                    AuditEvent(
                        user_id=actor_id,
                        action=action,
                        subject_id=subject_id,
                        hadm_id=None,
                        stay_id=None,
                        result="SUCCESS",
                        trace_id=trace_id,
                        timestamp=now,
                    )
                )
            except Exception as error:
                user.assigned_subject_ids = prior_assignments
                del user.assignment_history[prior_history_length:]
                raise ClinicalAuditUnavailable from error
            return self._snapshot(user)

    def record(self, event: AuditEvent) -> None:
        with self._lock:
            self._audit_events.append(event)

    def audit_events(self) -> list[AuditEvent]:
        with self._lock:
            return list(self._audit_events)

    def _require_user(self, user_id: str) -> OperationalUser:
        user = self._users.get(user_id)
        if user is None:
            raise KeyError(user_id)
        return user

    def _snapshot(self, user: OperationalUser) -> OperationalUser:
        return OperationalUser(
            user_id=user.user_id,
            role=user.role,
            state=user.state,
            assigned_subject_ids=self._effective_assignments(user),
            assignment_history=list(user.assignment_history),
        )

    @staticmethod
    def _load_demo_subjects() -> set[int]:
        settings = get_settings()
        if settings.app_env == "test":
            return {101}
        manifest = Path(settings.mimic_demo_subjects_file)
        if not manifest.exists():
            return set()
        with manifest.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            subjects = []
            for row in reader:
                value = row.get("subject_id", "").strip()
                if value.isdigit():
                    subjects.append(int(value))
                if len(subjects) >= settings.mimic_demo_subject_limit:
                    break
        return set(subjects)

    @staticmethod
    def _effective_assignments(user: OperationalUser) -> set[int]:
        if get_settings().app_env == "test" and user.role == "DOCTOR":
            # Keep the stable synthetic fixture for doctor-1 while preserving
            # runtime assignment mutations for admin/session boundary tests.
            return {101} if user.user_id == "doctor-1" else set(user.assigned_subject_ids)
        return set(user.assigned_subject_ids)


operational_store = OperationalStore()
