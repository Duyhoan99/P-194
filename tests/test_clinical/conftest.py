import pytest

from src.clinical.audit import InMemoryAuditSink
from src.clinical.errors import ClinicalAccessDenied
from src.clinical.schemas import AccessContext


def allowed_context() -> AccessContext:
    return AccessContext(
        user_id="doctor-1",
        role="DOCTOR",
        assigned_subject_ids={101},
        trace_id="trace-allowed",
    )


class DenyAllChecker:
    def can_access(self, context: AccessContext, subject_id: int) -> bool:
        return False

    def assert_access(self, context: AccessContext, subject_id: int) -> None:
        raise ClinicalAccessDenied


@pytest.fixture
def audit_sink() -> InMemoryAuditSink:
    return InMemoryAuditSink()
