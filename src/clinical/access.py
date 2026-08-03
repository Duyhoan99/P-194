"""Access checks for clinical retrieval scopes."""

from collections.abc import Mapping
from typing import Protocol

from src.clinical.errors import ClinicalAccessDenied
from src.clinical.schemas import AccessContext


class AssignmentChecker(Protocol):
    """Checks whether an authenticated context can read a subject."""

    def can_access(self, context: AccessContext, subject_id: int) -> bool:
        """Return whether the context may access the requested subject."""

    def assert_access(self, context: AccessContext, subject_id: int) -> None:
        """Raise when the context may not access the requested subject."""


class DemoAssignmentProvider:
    """Fail-closed assignment checker for local development."""

    def __init__(self, assignments: Mapping[str, set[int]], admin_users: set[str]) -> None:
        self._assignments = {user_id: set(subject_ids) for user_id, subject_ids in assignments.items()}
        self._admin_users = set(admin_users)

    def can_access(self, context: AccessContext, subject_id: int) -> bool:
        if context.role == "ADMIN":
            return context.user_id in self._admin_users

        assigned_by_provider = self._assignments.get(context.user_id, set())
        return subject_id in assigned_by_provider and subject_id in context.assigned_subject_ids

    def assert_access(self, context: AccessContext, subject_id: int) -> None:
        if not self.can_access(context, subject_id):
            raise ClinicalAccessDenied
