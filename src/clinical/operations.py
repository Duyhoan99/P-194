"""Safe local user, assignment, and audit state for the demo."""

from __future__ import annotations

import json
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
AssignmentAction = Literal["ASSIGN_PATIENT", "REVOKE_PATIENT"]


@dataclass(frozen=True)
class AssignmentHistoryEntry:
    patient_id: str
    action: AssignmentAction
    actor_id: str
    timestamp: datetime


@dataclass
class OperationalUser:
    user_id: str
    role: OperationalRole
    state: AccountState = "ACTIVE"
    assigned_patient_ids: set[str] = field(default_factory=set)
    assignment_history: list[AssignmentHistoryEntry] = field(default_factory=list)


class OperationalStore:
    """In-memory operational metadata; clinical content remains in DemoRepository."""

    def __init__(self) -> None:
        demo_patients = self._load_demo_patients()
        self._users: dict[str, OperationalUser] = {
            "doctor-1": OperationalUser("doctor-1", "DOCTOR", assigned_patient_ids=demo_patients),
            "usr_doctor_demo": OperationalUser(
                "usr_doctor_demo", "DOCTOR", assigned_patient_ids=demo_patients
            ),
            "doctor-2": OperationalUser("doctor-2", "DOCTOR"),
            "admin-1": OperationalUser("admin-1", "ADMIN"),
            "steward-1": OperationalUser("steward-1", "DATA_STEWARD"),
            "compliance-1": OperationalUser("compliance-1", "COMPLIANCE"),
        }
        self._audit_events: list[AuditEvent] = []
        self._lock = RLock()

    def users(self) -> list[OperationalUser]:
        with self._lock:
            return [self._snapshot(user) for user in sorted(self._users.values(), key=lambda item: item.user_id)]

    def get_user(self, user_id: str) -> OperationalUser:
        with self._lock:
            return self._snapshot(self._require_user(user_id))

    def session_identity(self, user_id: str) -> tuple[OperationalRole, set[str]] | None:
        with self._lock:
            user = self._users.get(user_id)
            if user is None or user.state != "ACTIVE":
                return None
            return user.role, set(user.assigned_patient_ids)

    def assignments(self) -> dict[str, set[str]]:
        with self._lock:
            return {
                user.user_id: set(user.assigned_patient_ids)
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
        patient_id: str,
        actor_id: str,
        trace_id: str,
        action: AssignmentAction,
    ) -> OperationalUser:
        patient_id = patient_id.strip()
        if not patient_id:
            raise ValueError("Patient ID is required")
        with self._lock:
            user = self._require_user(user_id)
            if user.role != "DOCTOR":
                raise ValueError("Assignments may only target doctor accounts")
            previous = set(user.assigned_patient_ids)
            history_length = len(user.assignment_history)
            now = datetime.now(UTC)
            if action == "ASSIGN_PATIENT":
                user.assigned_patient_ids.add(patient_id)
            else:
                user.assigned_patient_ids.discard(patient_id)
            user.assignment_history.append(AssignmentHistoryEntry(patient_id, action, actor_id, now))
            try:
                self.record(
                    AuditEvent(
                        user_id=actor_id,
                        action=action,
                        patient_id=patient_id,
                        result="SUCCESS",
                        trace_id=trace_id,
                        timestamp=now,
                    )
                )
            except Exception as error:
                user.assigned_patient_ids = previous
                del user.assignment_history[history_length:]
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

    @staticmethod
    def _snapshot(user: OperationalUser) -> OperationalUser:
        return OperationalUser(
            user_id=user.user_id,
            role=user.role,
            state=user.state,
            assigned_patient_ids=set(user.assigned_patient_ids),
            assignment_history=list(user.assignment_history),
        )

    @staticmethod
    def _load_demo_patients() -> set[str]:
        manifest = Path(get_settings().demo_data_dir) / "dataset_manifest.json"
        if not manifest.exists():
            return set()
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        return {
            str(item["patient_id"])
            for item in payload.get("patients", [])
            if isinstance(item, dict) and item.get("patient_id")
        }


operational_store = OperationalStore()
