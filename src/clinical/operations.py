"""Safe, local operational metadata for the development/test vertical slice."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from src.clinical.audit import AuditEvent

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
    """In-memory operational state used only by the synthetic demo surface."""

    def __init__(self) -> None:
        self._users: dict[str, OperationalUser] = {
            "doctor-1": OperationalUser("doctor-1", "DOCTOR", assigned_subject_ids={101}),
            "doctor-2": OperationalUser("doctor-2", "DOCTOR"),
            "admin-1": OperationalUser("admin-1", "ADMIN"),
            "steward-1": OperationalUser("steward-1", "DATA_STEWARD"),
            "compliance-1": OperationalUser("compliance-1", "COMPLIANCE"),
        }
        self._audit_events: list[AuditEvent] = []

    def users(self) -> list[OperationalUser]:
        return sorted(self._users.values(), key=lambda user: user.user_id)

    def get_user(self, user_id: str) -> OperationalUser:
        user = self._users.get(user_id)
        if user is None:
            raise KeyError(user_id)
        return user

    def assignments(self) -> dict[str, set[int]]:
        return {
            user.user_id: set(user.assigned_subject_ids)
            for user in self._users.values()
            if user.role == "DOCTOR" and user.state == "ACTIVE"
        }

    def admin_users(self) -> set[str]:
        return {
            user.user_id
            for user in self._users.values()
            if user.role == "ADMIN" and user.state == "ACTIVE"
        }

    def grant_assignment(self, user_id: str, subject_id: int, actor_id: str) -> OperationalUser:
        user = self.get_user(user_id)
        if user.role != "DOCTOR":
            raise ValueError("Assignments may only be changed for doctor accounts")
        user.assigned_subject_ids.add(subject_id)
        user.assignment_history.append(
            AssignmentHistoryEntry(subject_id, "ASSIGN_CLINICAL_SUBJECT", actor_id, datetime.now(UTC))
        )
        return user

    def revoke_assignment(self, user_id: str, subject_id: int, actor_id: str) -> OperationalUser:
        user = self.get_user(user_id)
        if user.role != "DOCTOR":
            raise ValueError("Assignments may only be changed for doctor accounts")
        user.assigned_subject_ids.discard(subject_id)
        user.assignment_history.append(
            AssignmentHistoryEntry(subject_id, "REVOKE_CLINICAL_SUBJECT", actor_id, datetime.now(UTC))
        )
        return user

    def record(self, event: AuditEvent) -> None:
        self._audit_events.append(event)

    def audit_events(self) -> list[AuditEvent]:
        return list(self._audit_events)


operational_store = OperationalStore()
