"""Authentication scope shared by the FHIR/PDF demo API."""

from typing import Literal

from pydantic import BaseModel, Field

from src.clinical.audit import TraceId


class AccessContext(BaseModel):
    user_id: str
    role: Literal["DOCTOR", "ADMIN", "DATA_STEWARD", "COMPLIANCE"]
    assigned_patient_ids: set[str] = Field(default_factory=set)
    trace_id: TraceId
