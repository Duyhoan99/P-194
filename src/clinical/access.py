"""Access checks for clinical retrieval scopes."""

import os
from collections.abc import Mapping
from typing import Protocol

import jwt
from fastapi import Request

from src.clinical.errors import ClinicalAccessDenied, ClinicalAuthNotConfigured
from src.clinical.schemas import AccessContext
from src.config import get_settings


class AuthProvider(Protocol):
    """Build an access context from a trusted upstream identity."""

    def authenticate(self, request: Request) -> AccessContext:
        """Authenticate without trusting client-supplied identity fields."""


class AssignmentProvider(Protocol):
    """Checks whether an authenticated context may read a clinical scope."""

    def can_access(
        self,
        context: AccessContext,
        subject_id: int,
        hadm_id: int | None = None,
        stay_id: int | None = None,
    ) -> bool:
        """Return whether the context may access the requested subject scope."""

    def assert_access(
        self,
        context: AccessContext,
        subject_id: int,
        hadm_id: int | None = None,
        stay_id: int | None = None,
    ) -> None:
        """Raise when the context may not access the requested subject."""


AssignmentChecker = AssignmentProvider


class ConfiguredAuthProvider:
    """Production JWT-based authentication provider."""

    def authenticate(self, request: Request) -> AccessContext:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise ClinicalAccessDenied("Missing or invalid Authorization header")

        token = auth_header.split("Bearer ")[1]
        # The cursor secret is guaranteed to be 32+ chars in production and serves as our symmetric key.
        secret = get_settings().clinical_cursor_secret
        
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError as e:
            raise ClinicalAccessDenied("Token has expired") from e
        except jwt.PyJWTError as e:
            raise ClinicalAccessDenied("Invalid token") from e

        user_id = payload.get("user_id")
        role = payload.get("role")
        assigned_subject_ids = payload.get("assigned_subject_ids", [])

        if not user_id or not role:
            raise ClinicalAccessDenied("Invalid token payload")

        return AccessContext(
            user_id=str(user_id),
            role=role,
            assigned_subject_ids=set(assigned_subject_ids),
            trace_id=getattr(request.state, "clinical_trace_id", ""),
        )


class JwtAssignmentProvider:
    """Checks assignments directly from the authenticated JWT context."""

    def can_access(
        self,
        context: AccessContext,
        subject_id: int,
        hadm_id: int | None = None,
        stay_id: int | None = None,
    ) -> bool:
        if context.role == "ADMIN":
            return True
        return subject_id in context.assigned_subject_ids

    def assert_access(
        self,
        context: AccessContext,
        subject_id: int,
        hadm_id: int | None = None,
        stay_id: int | None = None,
    ) -> None:
        if not self.can_access(context, subject_id, hadm_id, stay_id):
            raise ClinicalAccessDenied


class DemoAssignmentProvider:
    """Fail-closed assignment checker for local development."""

    def __init__(self, assignments: Mapping[str, set[int]], admin_users: set[str]) -> None:
        if os.getenv("APP_ENV", "").lower() == "production" or get_settings().app_env == "production":
            raise ClinicalAuthNotConfigured("Demo assignment provider is disabled in production")
        self._assignments = {user_id: set(subject_ids) for user_id, subject_ids in assignments.items()}
        self._admin_users = set(admin_users)

    def can_access(
        self,
        context: AccessContext,
        subject_id: int,
        hadm_id: int | None = None,
        stay_id: int | None = None,
    ) -> bool:
        del hadm_id, stay_id
        if context.role == "ADMIN":
            return context.user_id in self._admin_users

        assigned_by_provider = self._assignments.get(context.user_id, set())
        return subject_id in assigned_by_provider and subject_id in context.assigned_subject_ids

    def assert_access(
        self,
        context: AccessContext,
        subject_id: int,
        hadm_id: int | None = None,
        stay_id: int | None = None,
    ) -> None:
        if not self.can_access(context, subject_id, hadm_id, stay_id):
            raise ClinicalAccessDenied
