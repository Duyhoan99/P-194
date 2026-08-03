"""Role-separated administrative and compliance metadata endpoints."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.dependencies import get_access_context, get_operational_store
from src.clinical.audit import AuditAction, AuditResult
from src.clinical.errors import ClinicalAccessDenied
from src.clinical.operations import OperationalStore, OperationalUser
from src.clinical.schemas import AccessContext

router = APIRouter(prefix="/admin", tags=["admin"])


class AssignmentRequest(BaseModel):
    subject_id: int = Field(gt=0)


class AssignmentHistoryResponse(BaseModel):
    subject_reference: str
    action: Literal["ASSIGN_CLINICAL_SUBJECT", "REVOKE_CLINICAL_SUBJECT"]
    actor: str
    timestamp: datetime


class UserResponse(BaseModel):
    user_id: str
    role: str
    state: Literal["ACTIVE", "LOCKED"]
    assignments: list[str]
    assignment_history: list[AssignmentHistoryResponse]


class UsersResponse(BaseModel):
    users: list[UserResponse]
    trace_id: str


class AuditEntryResponse(BaseModel):
    actor: str
    action: AuditAction
    subject_reference: str
    timestamp: datetime
    result: AuditResult
    trace_id: str


class AuditResponse(BaseModel):
    events: list[AuditEntryResponse]
    trace_id: str


def _require_role(context: AccessContext, *roles: str) -> None:
    if context.role not in roles:
        raise ClinicalAccessDenied


def _subject_reference(subject_id: int) -> str:
    return f"subject-{subject_id}"


def _user_response(user: OperationalUser) -> UserResponse:
    return UserResponse(
        user_id=user.user_id,
        role=user.role,
        state=user.state,
        assignments=[_subject_reference(subject_id) for subject_id in sorted(user.assigned_subject_ids)],
        assignment_history=[
            AssignmentHistoryResponse(
                subject_reference=_subject_reference(entry.subject_id),
                action=entry.action,
                actor=entry.actor_id,
                timestamp=entry.timestamp,
            )
            for entry in user.assignment_history
        ],
    )


@router.get("/users", response_model=UsersResponse)
def list_users(
    context: AccessContext = Depends(get_access_context),
    store: OperationalStore = Depends(get_operational_store),
) -> UsersResponse:
    _require_role(context, "ADMIN")
    return UsersResponse(users=[_user_response(user) for user in store.users()], trace_id=context.trace_id)


@router.post("/users/{user_id}/assignments", response_model=UserResponse)
def grant_assignment(
    user_id: str,
    payload: AssignmentRequest,
    context: AccessContext = Depends(get_access_context),
    store: OperationalStore = Depends(get_operational_store),
) -> UserResponse:
    _require_role(context, "ADMIN")
    try:
        user = store.change_assignment(
            user_id, payload.subject_id, context.user_id, context.trace_id, "ASSIGN_CLINICAL_SUBJECT"
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Assignments may only target doctor accounts.") from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Operational user was not found.") from error
    return _user_response(user)


@router.delete("/users/{user_id}/assignments/{subject_id}", response_model=UserResponse)
def revoke_assignment(
    user_id: str,
    subject_id: int,
    context: AccessContext = Depends(get_access_context),
    store: OperationalStore = Depends(get_operational_store),
) -> UserResponse:
    _require_role(context, "ADMIN")
    if subject_id <= 0:
        raise HTTPException(status_code=422, detail="Subject reference is invalid.")
    try:
        user = store.change_assignment(
            user_id, subject_id, context.user_id, context.trace_id, "REVOKE_CLINICAL_SUBJECT"
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Assignments may only target doctor accounts.") from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Operational user was not found.") from error
    return _user_response(user)


@router.get("/audit", response_model=AuditResponse)
def list_audit_events(
    actor: str | None = Query(default=None, max_length=128),
    action: AuditAction | None = None,
    result: AuditResult | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    context: AccessContext = Depends(get_access_context),
    store: OperationalStore = Depends(get_operational_store),
) -> AuditResponse:
    _require_role(context, "ADMIN", "COMPLIANCE")
    if from_time and to_time and from_time > to_time:
        raise HTTPException(status_code=422, detail="Audit time window is invalid.")
    events = [
        event
        for event in store.audit_events()
        if (actor is None or event.user_id == actor)
        and (action is None or event.action == action)
        and (result is None or event.result == result)
        and (from_time is None or event.timestamp >= from_time)
        and (to_time is None or event.timestamp <= to_time)
    ]
    return AuditResponse(
        events=[
            AuditEntryResponse(
                actor=event.user_id,
                action=event.action,
                subject_reference=_subject_reference(event.subject_id),
                timestamp=event.timestamp,
                result=event.result,
                trace_id=event.trace_id,
            )
            for event in events
        ],
        trace_id=context.trace_id,
    )
