"""Pydantic contracts shared by clinical retrieval components."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.clinical.audit import TraceId
from src.config import get_settings

ClinicalStatus = Literal["SUCCESS", "PARTIAL", "EMPTY", "DENIED", "NOT_LOADED"]


class ClinicalQuery(BaseModel):
    subject_id: int
    hadm_id: int | None = None
    stay_id: int | None = None
    from_time: datetime | None = None
    to_time: datetime | None = None
    limit: int = 200

    @field_validator("subject_id", "hadm_id", "stay_id")
    @classmethod
    def ids_must_be_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("IDs must be positive")
        return value

    @field_validator("limit")
    @classmethod
    def limit_must_be_bounded(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("limit must be positive")
        if value > get_settings().clinical_max_limit:
            raise ValueError("limit exceeds clinical maximum")
        return value

    @model_validator(mode="after")
    def time_window_must_be_ordered(self) -> "ClinicalQuery":
        if self.from_time is not None and self.to_time is not None:
            from_time_aware = self.from_time.tzinfo is not None and self.from_time.utcoffset() is not None
            to_time_aware = self.to_time.tzinfo is not None and self.to_time.utcoffset() is not None
            if from_time_aware != to_time_aware:
                raise ValueError("from_time and to_time must have matching timezone awareness")
            if self.from_time > self.to_time:
                raise ValueError("from_time must not be after to_time")
        return self


class SourceLineage(BaseModel):
    dataset: Literal["MIMIC-IV"]
    version: Literal["3.1"]
    module: Literal["hosp", "icu"]
    table: str
    source_row_key: str
    subject_id: int
    hadm_id: int | None = None
    stay_id: int | None = None
    event_time: datetime | None = None


class EvidenceRecord(BaseModel):
    record_type: str
    data: dict[str, Any]
    lineage: SourceLineage
    related_sources: list[SourceLineage] = Field(default_factory=list)


class ClinicalResponse(BaseModel):
    status: ClinicalStatus
    records: list[EvidenceRecord]
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    trace_id: str


class AccessContext(BaseModel):
    user_id: str
    role: Literal["DOCTOR", "ADMIN"]
    assigned_subject_ids: set[int] = Field(default_factory=set)
    trace_id: TraceId
