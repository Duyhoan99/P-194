"""Authentication and patient-assignment checks for the FHIR/PDF workflow."""

import os
from collections.abc import Mapping
from typing import Protocol

import jwt
from fastapi import Request

from src.clinical.errors import ClinicalAccessDenied, ClinicalAuthNotConfigured
from src.clinical.schemas import AccessContext
from src.config import get_settings


class AuthProvider(Protocol):
    def authenticate(self, request: Request) -> AccessContext: ...


class AssignmentProvider(Protocol):
    def can_access(self, context: AccessContext, patient_id: str) -> bool: ...

    def assert_access(self, context: AccessContext, patient_id: str) -> None: ...


AssignmentChecker = AssignmentProvider


class ConfiguredAuthProvider:
    """Validate a production bearer token created by the configured identity layer."""

    def authenticate(self, request: Request) -> AccessContext:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise ClinicalAccessDenied("Missing or invalid Authorization header")
        try:
            payload = jwt.decode(
                auth_header.removeprefix("Bearer "),
                get_settings().session_secret,
                algorithms=["HS256"],
            )
        except jwt.ExpiredSignatureError as error:
            raise ClinicalAccessDenied("Token has expired") from error
        except jwt.PyJWTError as error:
            raise ClinicalAccessDenied("Invalid token") from error

        user_id = payload.get("user_id")
        role = payload.get("role")
        if not user_id or not role:
            raise ClinicalAccessDenied("Invalid token payload")
        return AccessContext(
            user_id=str(user_id),
            role=role,
            assigned_patient_ids={str(value) for value in payload.get("assigned_patient_ids", [])},
            trace_id=getattr(request.state, "clinical_trace_id", ""),
        )


class JwtAssignmentProvider:
    def can_access(self, context: AccessContext, patient_id: str) -> bool:
        return context.role == "ADMIN" or patient_id in context.assigned_patient_ids

    def assert_access(self, context: AccessContext, patient_id: str) -> None:
        if not self.can_access(context, patient_id):
            raise ClinicalAccessDenied


class DemoAssignmentProvider:
    """Use only server-owned patient assignments in development and tests."""

    def __init__(self, assignments: Mapping[str, set[str]], admin_users: set[str]) -> None:
        if os.getenv("APP_ENV", "").lower() == "production" or get_settings().app_env == "production":
            raise ClinicalAuthNotConfigured("Demo assignment provider is disabled in production")
        self._assignments = {user_id: set(patient_ids) for user_id, patient_ids in assignments.items()}
        self._admin_users = set(admin_users)

    def can_access(self, context: AccessContext, patient_id: str) -> bool:
        if context.role == "ADMIN":
            return context.user_id in self._admin_users
        return (
            patient_id in self._assignments.get(context.user_id, set())
            and patient_id in context.assigned_patient_ids
        )

    def assert_access(self, context: AccessContext, patient_id: str) -> None:
        if not self.can_access(context, patient_id):
            raise ClinicalAccessDenied
