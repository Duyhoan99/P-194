"""Scope-only audit events for clinical retrieval."""

from datetime import datetime
from typing import Protocol

from loguru import logger
from pydantic import BaseModel, ConfigDict


class AuditEvent(BaseModel):
    """A clinical access event that deliberately excludes clinical values."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    action: str
    subject_id: int
    hadm_id: int | None
    stay_id: int | None
    result: str
    trace_id: str
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


class StructuredAuditSink:
    """Emits scope-only audit fields through the structured application logger."""

    def record(self, event: AuditEvent) -> None:
        logger.bind(**event.model_dump(mode="json")).info("clinical_audit_event")
