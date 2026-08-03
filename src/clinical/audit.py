"""Scope-only audit events for clinical retrieval."""

from datetime import datetime
from typing import Annotated, Literal, Protocol

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

AuditAction = Literal[
    "VIEW_PATIENT_OVERVIEW",
    "VIEW_ENCOUNTER_TIMELINE",
    "VIEW_DIAGNOSES_AND_PROCEDURES",
    "VIEW_LABS",
    "VIEW_LABORATORY_RESULTS",
    "VIEW_MICROBIOLOGY",
    "VIEW_MICROBIOLOGY_RESULTS",
    "VIEW_ICU_EVENTS",
]
AuditResult = Literal["SUCCESS", "PARTIAL", "EMPTY", "DENIED", "NOT_LOADED", "ERROR"]
TraceId = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")]


class AuditEvent(BaseModel):
    """A clinical access event that deliberately excludes clinical values."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    action: AuditAction
    subject_id: int
    hadm_id: int | None
    stay_id: int | None
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


class StructuredAuditSink:
    """Emits scope-only audit fields through the structured application logger."""

    def record(self, event: AuditEvent) -> None:
        logger.bind(**event.model_dump(mode="json")).info("clinical_audit_event")
