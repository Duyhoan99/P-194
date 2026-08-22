"""FastAPI dependencies for the active FHIR/PDF demo workflow."""

from pathlib import Path
from uuid import uuid4

from fastapi import Request

from src.clinical.access import AuthProvider, ConfiguredAuthProvider
from src.clinical.audit import AuditSink, CompositeAuditSink, StructuredAuditSink
from src.clinical.demo_auth import DemoSessionProvider
from src.clinical.demo_repository import DemoRepository
from src.clinical.errors import ClinicalDatabaseUnavailable
from src.clinical.operations import OperationalStore, operational_store
from src.clinical.schemas import AccessContext
from src.config import get_settings


def get_audit_sink() -> AuditSink:
    if get_settings().app_env in {"development", "test"}:
        return CompositeAuditSink(operational_store, StructuredAuditSink())
    return StructuredAuditSink()


def get_operational_store() -> OperationalStore:
    if get_settings().app_env not in {"development", "test"}:
        raise ClinicalDatabaseUnavailable
    return operational_store


def get_access_context(request: Request) -> AccessContext:
    request.state.clinical_trace_id = str(uuid4())
    provider: AuthProvider
    if get_settings().app_env in {"development", "test"}:
        provider = DemoSessionProvider()
    else:
        provider = ConfiguredAuthProvider()
    return provider.authenticate(request)


_demo_repo_instance: DemoRepository | None = None


def get_demo_repository() -> DemoRepository:
    global _demo_repo_instance
    if _demo_repo_instance is None:
        state_path = Path(get_settings().demo_data_dir) / ".runtime" / "review_state.json"
        _demo_repo_instance = DemoRepository(state_path=state_path)
    return _demo_repo_instance
