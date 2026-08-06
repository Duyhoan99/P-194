from datetime import UTC, datetime

import pytest
from loguru import logger
from pydantic import ValidationError

from src.clinical.access import AuthProvider, ConfiguredAuthProvider, DemoAssignmentProvider
from src.clinical.audit import AuditEvent, InMemoryAuditSink, StructuredAuditSink
from src.clinical.errors import ClinicalAccessDenied, ClinicalAuthNotConfigured
from src.clinical.schemas import AccessContext
from src.config import get_settings

TRACE_ID = "123e4567-e89b-42d3-a456-426614174000"


def test_doctor_can_access_only_assigned_subject():
    provider = DemoAssignmentProvider({"doctor-1": {10}}, set())
    context = AccessContext(user_id="doctor-1", role="DOCTOR", assigned_subject_ids={10}, trace_id=TRACE_ID)

    provider.assert_access(context, 10)

    with pytest.raises(ClinicalAccessDenied):
        provider.assert_access(context, 11)


def test_assignment_provider_accepts_encounter_and_stay_scope():
    provider = DemoAssignmentProvider({"doctor-1": {10}}, set())
    context = AccessContext(user_id="doctor-1", role="DOCTOR", assigned_subject_ids={10}, trace_id=TRACE_ID)

    provider.assert_access(context, 10, hadm_id=20, stay_id=30)


class MockRequest:
    def __init__(self):
        self.headers = {}

def test_configured_auth_provider_rejects_missing_header():
    provider: AuthProvider = ConfiguredAuthProvider()
    with pytest.raises(ClinicalAccessDenied, match="Missing or invalid Authorization header"):
        provider.authenticate(MockRequest())


def test_doctor_is_denied_when_context_assignment_set_is_empty():
    provider = DemoAssignmentProvider({"doctor-1": {10}}, set())
    context = AccessContext(user_id="doctor-1", role="DOCTOR", assigned_subject_ids=set(), trace_id=TRACE_ID)

    assert provider.can_access(context, 10) is False
    with pytest.raises(ClinicalAccessDenied):
        provider.assert_access(context, 10)


def test_non_admin_context_is_denied_even_when_client_claims_admin_role():
    provider = DemoAssignmentProvider({"doctor-1": {10}}, {"admin-1"})
    context = AccessContext(user_id="doctor-1", role="ADMIN", assigned_subject_ids={10}, trace_id=TRACE_ID)

    assert provider.can_access(context, 10) is False
    with pytest.raises(ClinicalAccessDenied):
        provider.assert_access(context, 10)


def test_explicitly_configured_admin_can_access_any_subject():
    provider = DemoAssignmentProvider({}, {"admin-1"})
    context = AccessContext(user_id="admin-1", role="ADMIN", trace_id=TRACE_ID)

    provider.assert_access(context, 999)


def test_demo_assignment_provider_rejects_production_configuration(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        with pytest.raises(ClinicalAuthNotConfigured):
            DemoAssignmentProvider({"doctor-1": {10}}, set())
    finally:
        get_settings.cache_clear()


def test_audit_sink_keeps_scope_only(audit_sink: InMemoryAuditSink):
    audit_sink.record(
        AuditEvent(
            user_id="doctor-1",
            action="VIEW_LABS",
            subject_id=10,
            hadm_id=20,
            stay_id=None,
            result="SUCCESS",
            trace_id=TRACE_ID,
            timestamp=datetime.now(UTC),
        )
    )

    assert audit_sink.events[0].subject_id == 10
    assert not hasattr(audit_sink.events[0], "raw_value")


def test_audit_event_rejects_raw_clinical_data_fields():
    with pytest.raises(ValidationError):
        AuditEvent(
            user_id="doctor-1",
            action="VIEW_LABS",
            subject_id=10,
            hadm_id=None,
            stay_id=None,
            result="SUCCESS",
            trace_id=TRACE_ID,
            timestamp=datetime.now(UTC),
            raw_value="7.1",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("action", "patient potassium is 7.1"),
        ("result", "Bearer secret-token"),
        ("trace_id", "secret-token"),
        ("trace_id", "123e4567-e89b-12d3-a456-426614174000"),
    ],
)
def test_audit_event_rejects_unapproved_scope_metadata(field: str, value: str):
    event = {
        "user_id": "doctor-1",
        "action": "VIEW_LABS",
        "subject_id": 10,
        "hadm_id": None,
        "stay_id": None,
        "result": "SUCCESS",
        "trace_id": TRACE_ID,
        "timestamp": datetime.now(UTC),
    }
    event[field] = value

    with pytest.raises(ValidationError):
        AuditEvent(**event)


def test_structured_audit_sink_emits_only_approved_fields():
    records = []
    handler_id = logger.add(lambda message: records.append(message.record))
    try:
        StructuredAuditSink().record(
            AuditEvent(
                user_id="doctor-1",
                action="VIEW_LABS",
                subject_id=10,
                hadm_id=20,
                stay_id=None,
                result="SUCCESS",
                trace_id=TRACE_ID,
                timestamp=datetime.now(UTC),
            )
        )
    finally:
        logger.remove(handler_id)

    assert records[0]["message"] == "clinical_audit_event"
    assert set(records[0]["extra"]) == {
        "user_id",
        "action",
        "subject_id",
        "hadm_id",
        "stay_id",
        "result",
        "trace_id",
        "timestamp",
    }
