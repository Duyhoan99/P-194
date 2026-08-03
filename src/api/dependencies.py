"""FastAPI dependencies for the clinical retrieval API."""

from uuid import uuid4

from fastapi import Request

from src.clinical.access import AssignmentChecker, AuthProvider, ConfiguredAuthProvider
from src.clinical.audit import StructuredAuditSink
from src.clinical.errors import ClinicalAccessDenied, ClinicalDatabaseUnavailable
from src.clinical.postgres_repository import PostgresClinicalRepository
from src.clinical.repository import ClinicalRepository, SQLiteClinicalRepository
from src.clinical.schemas import AccessContext
from src.clinical.service import ClinicalRetrievalService
from src.config import Settings, get_settings


class _FailClosedAssignmentChecker:
    """Service-side fallback that cannot grant access without configured auth."""

    def can_access(self, context: AccessContext, subject_id: int) -> bool:
        return False

    def assert_access(self, context: AccessContext, subject_id: int) -> None:
            raise ClinicalAccessDenied


def build_clinical_repository(settings: Settings) -> ClinicalRepository:
    """Select the configured clinical backend without an implicit fallback."""

    if settings.clinical_backend == "sqlite":
        return SQLiteClinicalRepository(
            settings.clinical_database_path,
            query_timeout_seconds=settings.clinical_query_timeout_seconds,
            source_dataset=settings.clinical_source_dataset,
            source_version=settings.clinical_source_version,
        )
    if settings.clinical_backend == "postgresql":
        return PostgresClinicalRepository(
            settings.clinical_postgres_dsn,
            query_timeout_seconds=settings.clinical_query_timeout_seconds,
            pool_size=settings.clinical_pool_size,
            source_dataset=settings.clinical_source_dataset,
            source_version=settings.clinical_source_version,
        )
    raise ClinicalDatabaseUnavailable


def get_clinical_service() -> ClinicalRetrievalService:
    """Build the production clinical service from configured infrastructure."""
    settings = get_settings()
    repository = build_clinical_repository(settings)
    access_checker: AssignmentChecker = _FailClosedAssignmentChecker()
    return ClinicalRetrievalService(repository, access_checker, StructuredAuditSink())


def get_access_context(request: Request) -> AccessContext:
    """Build context only through a trusted authentication integration.

    The default provider deliberately ignores all request headers and parameters.
    Tests and an organization-provided authentication provider replace it through
    FastAPI's dependency override mechanism.
    """
    request.state.clinical_trace_id = str(uuid4())
    provider: AuthProvider = ConfiguredAuthProvider()
    return provider.authenticate(request)
