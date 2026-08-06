"""FastAPI dependencies for the clinical retrieval API."""

from uuid import uuid4

from fastapi import Depends, Request

from src.clinical.access import (
    AssignmentChecker,
    AuthProvider,
    ConfiguredAuthProvider,
    DemoAssignmentProvider,
    JwtAssignmentProvider,
)
from src.clinical.agent import ClinicalAgent
from src.clinical.audit import AuditSink, CompositeAuditSink, StructuredAuditSink
from src.clinical.demo_auth import DemoSessionProvider
from src.clinical.errors import ClinicalAccessDenied, ClinicalDatabaseUnavailable
from src.clinical.operations import OperationalStore, operational_store
from src.clinical.postgres_repository import PostgresClinicalRepository
from src.clinical.repository import ClinicalRepository, SQLiteClinicalRepository
from src.clinical.review import ReviewService
from src.clinical.schemas import AccessContext
from src.clinical.service import ClinicalRetrievalService
from src.clinical.summary_generator import DeterministicDemoSummaryGenerator
from src.clinical.summary_repository import SQLiteSummaryRepository, SummaryRepository
from src.clinical.postgres_summary_repository import PostgresSummaryRepository
from src.clinical.summary_service import ClinicalSummaryService
from src.config import Settings, get_settings
from src.services.llm import get_structured_llm


class _FailClosedAssignmentChecker:
    """Service-side fallback that cannot grant access without configured auth."""

    def can_access(
        self,
        context: AccessContext,
        subject_id: int,
        hadm_id: int | None = None,
        stay_id: int | None = None,
    ) -> bool:
        del context, subject_id, hadm_id, stay_id
        return False

    def assert_access(
        self,
        context: AccessContext,
        subject_id: int,
        hadm_id: int | None = None,
        stay_id: int | None = None,
    ) -> None:
        del context, subject_id, hadm_id, stay_id
        raise ClinicalAccessDenied


class _UnavailableStructuredLLM:
    """Invocation stub that lets the Agent use its evidence-only fallback."""

    def invoke(self, _messages):
        raise RuntimeError("Structured LLM is not configured.")


def get_audit_sink() -> AuditSink:
    """Compose the development/test compliance feed with structured audit logging."""
    if get_settings().app_env in {"development", "test"}:
        return CompositeAuditSink(operational_store, StructuredAuditSink())
    return StructuredAuditSink()


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


def get_clinical_service(
    audit_sink: AuditSink = Depends(get_audit_sink),
) -> ClinicalRetrievalService:
    """Build the production clinical service from configured infrastructure."""
    settings = get_settings()
    repository = build_clinical_repository(settings)
    access_checker = get_assignment_checker()
    return ClinicalRetrievalService(repository, access_checker, audit_sink)


def get_assignment_checker() -> AssignmentChecker:
    """Select server-side demo assignments only outside production."""
    settings = get_settings()
    if settings.app_env in {"development", "test"}:
        return DemoAssignmentProvider(operational_store.assignments(), operational_store.admin_users())
    return JwtAssignmentProvider()


def get_operational_store() -> OperationalStore:
    """Expose synthetic operational metadata only outside production."""
    if get_settings().app_env not in {"development", "test"}:
        raise ClinicalDatabaseUnavailable
    return operational_store


def build_summary_repository(settings: Settings) -> SummaryRepository:
    """Select the configured summary backend."""
    if settings.summary_backend == "sqlite":
        if settings.app_env in {"development", "test"}:
            return SQLiteSummaryRepository(settings.summary_database_path)
        raise ClinicalDatabaseUnavailable
    if settings.summary_backend == "postgresql":
        return PostgresSummaryRepository(
            settings.summary_postgres_dsn,
            pool_size=settings.clinical_pool_size,
        )
    raise ClinicalDatabaseUnavailable


def get_summary_repository() -> SummaryRepository:
    return build_summary_repository(get_settings())


def get_summary_generator(
    clinical_service: ClinicalRetrievalService = Depends(get_clinical_service),
):
    settings = get_settings()
    if settings.summary_agent_backend == "langgraph":
        try:
            structured_llm = get_structured_llm()
        except Exception:
            structured_llm = _UnavailableStructuredLLM()
        return ClinicalAgent(
            clinical_service,
            structured_llm,
            fallback_generator=DeterministicDemoSummaryGenerator(),
        )
    return DeterministicDemoSummaryGenerator()


def get_summary_service(
    clinical_service: ClinicalRetrievalService = Depends(get_clinical_service),
    generator=Depends(get_summary_generator),
    audit_sink: AuditSink = Depends(get_audit_sink),
) -> ClinicalSummaryService:
    return ClinicalSummaryService(clinical_service, generator=generator, audit_sink=audit_sink)


def get_review_service(
    repository: SummaryRepository = Depends(get_summary_repository),
    assignments: AssignmentChecker = Depends(get_assignment_checker),
    summary_service: ClinicalSummaryService = Depends(get_summary_service),
    audit_sink: AuditSink = Depends(get_audit_sink),
) -> ReviewService:
    return ReviewService(repository, assignments, audit_sink, summary_service)


def get_access_context(request: Request) -> AccessContext:
    """Build context only through a trusted authentication integration.

    The default provider deliberately ignores all request headers and parameters.
    Tests and an organization-provided authentication provider replace it through
    FastAPI's dependency override mechanism.
    """
    request.state.clinical_trace_id = str(uuid4())
    provider: AuthProvider
    if get_settings().app_env in {"development", "test"}:
        provider = DemoSessionProvider()
    else:
        provider = ConfiguredAuthProvider()
    return provider.authenticate(request)
