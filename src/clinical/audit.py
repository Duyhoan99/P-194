"""Scope-only audit events for the clinical review workflow."""

from datetime import datetime
from typing import Annotated, Literal, Protocol

# pyrefly: ignore [missing-import]
from loguru import logger

# pyrefly: ignore [missing-import]
from pydantic import BaseModel, ConfigDict, Field

AuditAction = Literal[
    "VIEW_PATIENT_OVERVIEW",
    "VIEW_ENCOUNTER_TIMELINE",
    "GENERATE_REVIEW",
    "EDIT_REVIEW",
    "REJECT_REVIEW",
    "APPROVE_REVIEW",
    "EXPORT_REVIEW",
    "ASSIGN_PATIENT",
    "REVOKE_PATIENT",
    "DELETE_PATIENT",
]
AuditResult = Literal["SUCCESS", "PARTIAL", "EMPTY", "DENIED", "NOT_LOADED", "ERROR"]
TraceId = Annotated[str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")]


class AuditEvent(BaseModel):
    """A clinical access event that deliberately excludes clinical values."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    action: AuditAction
    patient_id: str
    result: AuditResult
    trace_id: TraceId
    timestamp: datetime


class AuditSink(Protocol):
    """Records a scope-only audit event."""

    def record(self, event: AuditEvent) -> None:
        """Persist or emit an audit event."""


class InMemoryAuditSink:
    """In-memory audit sink for tests and local development."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)


class CompositeAuditSink:
    """Writes the same scope-only event to each configured audit destination."""

    def __init__(self, *sinks: AuditSink) -> None:
        self._sinks = sinks

    def record(self, event: AuditEvent) -> None:
        for sink in self._sinks:
            sink.record(event)


class StructuredAuditSink:
    """Emits scope-only audit fields through the structured application logger."""

    def record(self, event: AuditEvent) -> None:
        logger.bind(**event.model_dump(mode="json")).info("clinical_audit_event")
