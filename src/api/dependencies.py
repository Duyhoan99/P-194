"""FastAPI dependencies for the clinical retrieval API."""

from uuid import uuid4

from fastapi import Request

from src.clinical.access import AssignmentChecker
from src.clinical.audit import StructuredAuditSink
from src.clinical.errors import ClinicalAccessDenied, ClinicalAuthNotConfigured
from src.clinical.repository import SQLiteClinicalRepository
from src.clinical.schemas import AccessContext
from src.clinical.service import ClinicalRetrievalService
from src.config import get_settings


class _FailClosedAssignmentChecker:
    """Service-side fallback that cannot grant access without configured auth."""

    def can_access(self, context: AccessContext, subject_id: int) -> bool:
        return False

    def assert_access(self, context: AccessContext, subject_id: int) -> None:
        raise ClinicalAccessDenied


def get_clinical_service() -> ClinicalRetrievalService:
    """Build the production clinical service from configured infrastructure."""
    settings = get_settings()
    repository = SQLiteClinicalRepository(
        settings.clinical_database_path,
        query_timeout_seconds=settings.clinical_query_timeout_seconds,
    )
    access_checker: AssignmentChecker = _FailClosedAssignmentChecker()
    return ClinicalRetrievalService(repository, access_checker, StructuredAuditSink())


def get_access_context(request: Request) -> AccessContext:
    """Reject requests until a trusted authentication integration is configured.

    This dependency deliberately ignores all request headers and parameters. Tests
    and explicitly configured authentication providers replace it through FastAPI's
    dependency override mechanism.
    """
    request.state.clinical_trace_id = str(uuid4())
    raise ClinicalAuthNotConfigured
