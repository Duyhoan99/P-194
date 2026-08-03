import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.clinical.access import DemoAssignmentProvider
from src.clinical.audit import AuditEvent, InMemoryAuditSink
from src.clinical.errors import ClinicalAccessDenied, ReviewPolicyError
from src.clinical.review import ReviewChecklist, ReviewService
from src.clinical.schemas import AccessContext, ClinicalQuery, SourceLineage
from src.clinical.summary_repository import SQLiteSummaryRepository
from src.clinical.summary_schemas import Citation, Claim, ClinicalSummaryDraft, Conflict
from src.clinical.summary_service import ClinicalSummaryService
from src.config import Settings, get_settings
from tests.clinical_fixtures import create_mock_clinical_db
from tests.test_clinical.conftest import TEST_TRACE_ID, allowed_context

ALTERNATE_TRACE_ID = "223e4567-e89b-42d3-a456-426614174000"


def context_for_subject(subject_id: int) -> AccessContext:
    return AccessContext(
        user_id="doctor-1",
        role="DOCTOR",
        assigned_subject_ids={subject_id},
        trace_id=TEST_TRACE_ID,
    )


def context_with_trace(trace_id: str) -> AccessContext:
    return allowed_context().model_copy(update={"trace_id": trace_id})


class PassingEvidenceValidator:
    """Keeps review-policy unit tests focused on state transitions, not retrieval fixtures."""

    def validate_edit(self, context, original, patch) -> None:
        del context, original, patch


@pytest.fixture
def summary_repo(tmp_path) -> SQLiteSummaryRepository:
    return SQLiteSummaryRepository(tmp_path / "application.sqlite")


@pytest.fixture
def valid_draft() -> ClinicalSummaryDraft:
    citation_id = "labevent_id=9001"
    return ClinicalSummaryDraft(
        summary_id=uuid4(),
        subject_id=101,
        hadm_id=5001,
        stay_id=None,
        status="DRAFT",
        sections={
            "Clinical Overview": [
                Claim(
                    claim_id="claim-1",
                    section="Clinical Overview",
                    text="Synthetic reviewed claim.",
                    citation_ids=[citation_id],
                    status="VALID",
                )
            ]
        },
        citations=[
            Citation(
                citation_id=citation_id,
                lineage=SourceLineage(
                    dataset="MIMIC-IV",
                    version="3.1",
                    module="hosp",
                    table="labevents",
                    source_row_key=citation_id,
                    subject_id=101,
                    hadm_id=5001,
                ),
                supported_fields=["value"],
            )
        ],
        conflicts=[],
        limitations=["AI output requires clinician review."],
        trace_id=TEST_TRACE_ID,
    )


@pytest.fixture
def review_service(summary_repo: SQLiteSummaryRepository) -> ReviewService:
    return ReviewService(
        summary_repo,
        DemoAssignmentProvider({"doctor-1": {101}}, set()),
        InMemoryAuditSink(),
        PassingEvidenceValidator(),
    )


def complete_checklist() -> ReviewChecklist:
    return ReviewChecklist(
        reviewed_summary=True,
        checked_critical_evidence=True,
        understands_ai_limitations=True,
        confirms_edits=True,
    )


def edit_event(draft: ClinicalSummaryDraft) -> AuditEvent:
    return AuditEvent(
        user_id="doctor-1",
        action="EDIT_CLINICAL_SUMMARY",
        subject_id=draft.subject_id,
        hadm_id=draft.hadm_id,
        stay_id=draft.stay_id,
        result="SUCCESS",
        trace_id=TEST_TRACE_ID,
        timestamp=datetime.now(UTC),
    )


def transition_event(draft: ClinicalSummaryDraft, action: str) -> AuditEvent:
    return AuditEvent(
        user_id="doctor-1",
        action=action,
        subject_id=draft.subject_id,
        hadm_id=draft.hadm_id,
        stay_id=draft.stay_id,
        result="SUCCESS",
        trace_id=TEST_TRACE_ID,
        timestamp=datetime.now(UTC),
    )


def test_create_and_list_versions(summary_repo: SQLiteSummaryRepository, valid_draft: ClinicalSummaryDraft):
    """Removing durable version rows would make a created draft disappear on lookup."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")
    updated = summary_repo.update_draft(
        created.summary_id,
        actor_id="doctor-1",
        patch=valid_draft.model_copy(update={"warnings": ["Doctor requested revision."]}),
        reason="Clarify warning",
        event=edit_event(valid_draft),
    )

    assert [version.version_number for version in summary_repo.list_versions(created.summary_id)] == [1, 2]
    assert updated.status == "NEEDS_REVISION"
    assert updated.reason == "Clarify warning"


def test_assigned_doctor_edit_creates_a_review_revision(summary_repo, review_service, valid_draft):
    """Bypassing the review service would allow an edit without assignment enforcement."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")

    edited = review_service.edit(
        created.summary_id,
        allowed_context(),
        valid_draft.model_copy(update={"warnings": ["Doctor requested revision."]}),
        "Clarify warning",
    )

    assert edited.status == "NEEDS_REVISION"
    assert edited.version_number == 2


def test_multiple_edits_can_be_followed_by_approval(summary_repo, review_service, valid_draft):
    """Leaving NEEDS_REVISION terminal would strand a doctor-edited summary."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")
    first_edit = review_service.edit(created.summary_id, allowed_context(), valid_draft, "First revision")
    second_edit = review_service.edit(
        created.summary_id,
        allowed_context(),
        first_edit.draft.model_copy(update={"warnings": ["Second revision."]}),
        "Second revision",
    )

    approved = review_service.approve(second_edit.summary_id, allowed_context(), complete_checklist())

    assert [version.status for version in summary_repo.list_versions(created.summary_id)] == [
        "DRAFT",
        "NEEDS_REVISION",
        "NEEDS_REVISION",
        "APPROVED",
    ]
    assert approved.status == "APPROVED"


def test_approved_version_is_immutable(summary_repo, review_service, valid_draft):
    """Allowing an approved row to change would erase the clinician-reviewed record."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")
    review_service.approve(created.summary_id, allowed_context(), complete_checklist())

    with pytest.raises(ReviewPolicyError):
        summary_repo.update_draft(
            created.summary_id,
            "doctor-1",
            valid_draft,
            "Change approved summary",
            edit_event(valid_draft),
        )

    assert summary_repo.get(created.summary_id).status == "APPROVED"


def test_unassigned_doctor_is_denied_before_review_repository_access(summary_repo, review_service, valid_draft):
    """Checking authorization after lookup could disclose an unassigned summary."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")

    with pytest.raises(ClinicalAccessDenied):
        review_service.approve(created.summary_id, context_for_subject(102), complete_checklist())


def test_denied_review_actions_are_audited_without_clinical_payloads(summary_repo, review_service, valid_draft):
    """Returning access denial before auditing would leave review attempts untraceable."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")
    denied = context_for_subject(102)

    with pytest.raises(ClinicalAccessDenied):
        review_service.edit(created.summary_id, denied, valid_draft, "Denied edit")
    with pytest.raises(ClinicalAccessDenied):
        review_service.reject(created.summary_id, denied, "Denied reject")
    with pytest.raises(ClinicalAccessDenied):
        review_service.approve(created.summary_id, denied, complete_checklist())
    with pytest.raises(ClinicalAccessDenied):
        review_service.export(created.summary_id, denied)

    with sqlite3.connect(summary_repo.db_path) as connection:
        rows = connection.execute(
            "SELECT action, result, subject_id FROM audit_events WHERE result = 'DENIED' ORDER BY rowid"
        ).fetchall()

    assert rows == [
        ("EDIT_CLINICAL_SUMMARY", "DENIED", 102),
        ("REJECT_CLINICAL_SUMMARY", "DENIED", 102),
        ("APPROVE_CLINICAL_SUMMARY", "DENIED", 102),
        ("EXPORT_CLINICAL_SUMMARY", "DENIED", 102),
    ]


def test_approval_requires_complete_checklist(summary_repo, review_service, valid_draft):
    """Skipping any human-review attestation would permit an unchecked approval."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")

    with pytest.raises(ReviewPolicyError):
        review_service.approve(
            created.summary_id,
            allowed_context(),
            ReviewChecklist(
                reviewed_summary=True,
                checked_critical_evidence=False,
                understands_ai_limitations=True,
                confirms_edits=True,
            ),
        )


def test_approval_rejects_claims_without_valid_citations(summary_repo, review_service, valid_draft):
    """A claim marked unsupported must not become part of an approved version."""
    invalid = valid_draft.model_copy(
        update={
            "sections": {
                "Clinical Overview": [
                    valid_draft.sections["Clinical Overview"][0].model_copy(update={"status": "UNSUPPORTED"})
                ]
            }
        }
    )
    created = summary_repo.create_draft(invalid, actor_id="doctor-1")

    with pytest.raises(ReviewPolicyError):
        review_service.approve(created.summary_id, allowed_context(), complete_checklist())


def test_fabricated_persisted_draft_cannot_be_approved_or_exported(summary_repo, assigned_service, audit_sink):
    """Approval validation must stop a manually persisted fabricated claim before any PDF export."""
    summary_service = ClinicalSummaryService(assigned_service, audit_sink=audit_sink)
    generated = summary_service.generate(allowed_context(), ClinicalQuery(subject_id=101))
    fabricated = generated.model_copy(
        update={
            "sections": {
                **generated.sections,
                "Laboratory Trends": [
                    generated.sections["Laboratory Trends"][0].model_copy(
                        update={"text": "Fabricated clinical conclusion."}
                    )
                ],
            }
        }
    )
    created = summary_repo.create_draft(fabricated, actor_id="doctor-1")
    evidence_validating_review = ReviewService(
        summary_repo,
        DemoAssignmentProvider({"doctor-1": {101}}, set()),
        InMemoryAuditSink(),
        summary_service,
    )

    with pytest.raises(ReviewPolicyError):
        evidence_validating_review.approve(created.summary_id, allowed_context(), complete_checklist())
    with pytest.raises(ReviewPolicyError):
        evidence_validating_review.export(created.summary_id, allowed_context())

    assert summary_repo.get(created.summary_id).status == "DRAFT"


def test_approval_requires_doctor_confirmed_conflict_resolution(summary_repo, review_service, valid_draft):
    """Trusting an AI-marked resolved conflict would bypass clinician confirmation."""
    conflicted = valid_draft.model_copy(
        update={
            "conflicts": [
                Conflict(
                    conflict_id="conflict-1",
                    topic="Medication discrepancy",
                    evidence_ids=["source-1", "source-2"],
                    status="RESOLVED",
                    resolution_note="AI-selected resolution",
                    resolved_by="summary-agent",
                )
            ]
        }
    )
    created = summary_repo.create_draft(conflicted, actor_id="doctor-1")

    with pytest.raises(ReviewPolicyError):
        review_service.approve(created.summary_id, allowed_context(), complete_checklist())

    confirmed = review_service.confirm_conflict(
        created.summary_id,
        allowed_context(),
        "conflict-1",
        "Doctor reviewed supporting evidence.",
    )
    approved = review_service.approve(confirmed.summary_id, allowed_context(), complete_checklist())

    assert approved.status == "APPROVED"
    assert confirmed.draft.conflicts[0].resolved_by == "doctor-1"
    with sqlite3.connect(summary_repo.db_path) as connection:
        resolution = connection.execute(
            "SELECT resolver_id, resolution_note FROM conflict_resolutions WHERE version_id = ?",
            (str(confirmed.version_id),),
        ).fetchone()
    assert resolution == ("doctor-1", "Doctor reviewed supporting evidence.")


def test_conflict_confirmation_is_atomic_with_version_and_success_audit(summary_repo, review_service, valid_draft):
    """A confirmation write failure must not leave a resolved version without provenance."""
    conflicted = valid_draft.model_copy(
        update={
            "conflicts": [
                Conflict(
                    conflict_id="conflict-1",
                    topic="Medication discrepancy",
                    evidence_ids=["source-1", "source-2"],
                    status="UNRESOLVED",
                )
            ]
        }
    )
    created = summary_repo.create_draft(conflicted, actor_id="doctor-1")
    with sqlite3.connect(summary_repo.db_path) as connection:
        connection.execute(
            """CREATE TRIGGER fail_conflict_confirmation BEFORE INSERT ON conflict_resolutions
               BEGIN SELECT RAISE(ABORT, 'conflict confirmation failed'); END"""
        )

    with pytest.raises(sqlite3.IntegrityError, match="conflict confirmation failed"):
        review_service.confirm_conflict(
            created.summary_id,
            allowed_context(),
            "conflict-1",
            "Doctor reviewed supporting evidence.",
        )

    current = summary_repo.get(created.summary_id)
    assert current.status == "DRAFT"
    assert current.draft.conflicts[0].status == "UNRESOLVED"
    with sqlite3.connect(summary_repo.db_path) as connection:
        resolution_count = connection.execute("SELECT COUNT(*) FROM conflict_resolutions").fetchone()[0]
        success_count = connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE action = 'RESOLVE_CLINICAL_CONFLICT' AND result = 'SUCCESS'"
        ).fetchone()[0]
    assert resolution_count == 0
    assert success_count == 0


def test_approval_is_atomic_with_checklist_and_success_audit(summary_repo, review_service, valid_draft):
    """An audit write failure must not leave an approved version without its checklist."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")
    with sqlite3.connect(summary_repo.db_path) as connection:
        connection.execute(
            """CREATE TRIGGER fail_approval_audit BEFORE INSERT ON audit_events
               WHEN NEW.action = 'APPROVE_CLINICAL_SUMMARY' AND NEW.result = 'SUCCESS'
               BEGIN SELECT RAISE(ABORT, 'audit write failed'); END"""
        )

    with pytest.raises(sqlite3.IntegrityError, match="audit write failed"):
        review_service.approve(created.summary_id, allowed_context(), complete_checklist())

    assert summary_repo.get(created.summary_id).status == "DRAFT"
    with sqlite3.connect(summary_repo.db_path) as connection:
        checklist_count = connection.execute("SELECT COUNT(*) FROM review_checklists").fetchone()[0]
        success_count = connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE action = 'APPROVE_CLINICAL_SUMMARY' AND result = 'SUCCESS'"
        ).fetchone()[0]
    assert checklist_count == 0
    assert success_count == 0


def test_rejection_is_atomic_with_success_audit(summary_repo, review_service, valid_draft):
    """A failed rejection audit must not leave a durable rejected version without provenance."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")
    with sqlite3.connect(summary_repo.db_path) as connection:
        connection.execute(
            """CREATE TRIGGER fail_rejection_audit BEFORE INSERT ON audit_events
               WHEN NEW.action = 'REJECT_CLINICAL_SUMMARY' AND NEW.result = 'SUCCESS'
               BEGIN SELECT RAISE(ABORT, 'rejection audit write failed'); END"""
        )

    with pytest.raises(sqlite3.IntegrityError, match="rejection audit write failed"):
        review_service.reject(created.summary_id, allowed_context(), "Needs evidence clarification")

    assert summary_repo.get(created.summary_id).status == "DRAFT"
    assert [version.version_number for version in summary_repo.list_versions(created.summary_id)] == [1]
    with sqlite3.connect(summary_repo.db_path) as connection:
        success_count = connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE action = 'REJECT_CLINICAL_SUMMARY' AND result = 'SUCCESS'"
        ).fetchone()[0]
    assert success_count == 0


def test_export_is_atomic_with_success_audit(summary_repo, review_service, valid_draft):
    """A failed export audit must not leave an exported version or current pointer behind."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")
    review_service.approve(created.summary_id, allowed_context(), complete_checklist())
    with sqlite3.connect(summary_repo.db_path) as connection:
        connection.execute(
            """CREATE TRIGGER fail_export_audit BEFORE INSERT ON audit_events
               WHEN NEW.action = 'EXPORT_CLINICAL_SUMMARY' AND NEW.result = 'SUCCESS'
               BEGIN SELECT RAISE(ABORT, 'export audit write failed'); END"""
        )

    with pytest.raises(sqlite3.IntegrityError, match="export audit write failed"):
        review_service.export(created.summary_id, allowed_context())

    assert summary_repo.get(created.summary_id).status == "APPROVED"
    assert [version.status for version in summary_repo.list_versions(created.summary_id)] == ["DRAFT", "APPROVED"]
    with sqlite3.connect(summary_repo.db_path) as connection:
        success_count = connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE action = 'EXPORT_CLINICAL_SUMMARY' AND result = 'SUCCESS'"
        ).fetchone()[0]
    assert success_count == 0


def test_transition_versions_and_audits_use_the_authenticated_request_trace(
    summary_repo, review_service, valid_draft
):
    """Terminal versions must not retain a previous request's trace identifier."""
    rejected = summary_repo.create_draft(valid_draft, actor_id="doctor-1")
    rejected_version = review_service.reject(
        rejected.summary_id, context_with_trace(ALTERNATE_TRACE_ID), "Needs evidence clarification"
    )

    approved = summary_repo.create_draft(valid_draft.model_copy(update={"summary_id": uuid4()}), actor_id="doctor-1")
    approved_version = review_service.approve(
        approved.summary_id, context_with_trace(ALTERNATE_TRACE_ID), complete_checklist()
    )

    exported = summary_repo.create_draft(valid_draft.model_copy(update={"summary_id": uuid4()}), actor_id="doctor-1")
    review_service.approve(exported.summary_id, allowed_context(), complete_checklist())
    exported_version = review_service.export(exported.summary_id, context_with_trace(ALTERNATE_TRACE_ID))

    assert [version.draft.trace_id for version in (rejected_version, approved_version, exported_version)] == [
        ALTERNATE_TRACE_ID,
        ALTERNATE_TRACE_ID,
        ALTERNATE_TRACE_ID,
    ]
    with sqlite3.connect(summary_repo.db_path) as connection:
        traces = connection.execute(
            """SELECT action, trace_id FROM audit_events
               WHERE action IN ('REJECT_CLINICAL_SUMMARY', 'APPROVE_CLINICAL_SUMMARY', 'EXPORT_CLINICAL_SUMMARY')
                 AND result = 'SUCCESS'
               ORDER BY rowid"""
        ).fetchall()
    assert traces == [
        ("REJECT_CLINICAL_SUMMARY", ALTERNATE_TRACE_ID),
        ("APPROVE_CLINICAL_SUMMARY", ALTERNATE_TRACE_ID),
        ("APPROVE_CLINICAL_SUMMARY", TEST_TRACE_ID),
        ("EXPORT_CLINICAL_SUMMARY", ALTERNATE_TRACE_ID),
    ]


def test_edit_is_atomic_with_success_audit(summary_repo, review_service, valid_draft):
    """An edit audit failure must roll back the new version and preserve the original traceable draft."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")
    with sqlite3.connect(summary_repo.db_path) as connection:
        connection.execute(
            """CREATE TRIGGER fail_edit_audit BEFORE INSERT ON audit_events
               WHEN NEW.action = 'EDIT_CLINICAL_SUMMARY' AND NEW.result = 'SUCCESS'
               BEGIN SELECT RAISE(ABORT, 'edit audit write failed'); END"""
        )

    with pytest.raises(sqlite3.IntegrityError, match="edit audit write failed"):
        review_service.edit(
            created.summary_id,
            allowed_context(),
            valid_draft.model_copy(update={"warnings": ["Attempted revision."]}),
            "Clarify warning",
        )

    assert summary_repo.get(created.summary_id).status == "DRAFT"
    assert [version.version_number for version in summary_repo.list_versions(created.summary_id)] == [1]
    with sqlite3.connect(summary_repo.db_path) as connection:
        success_count = connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE action = 'EDIT_CLINICAL_SUMMARY' AND result = 'SUCCESS'"
        ).fetchone()[0]
    assert success_count == 0


def test_invalid_transition_is_rejected(summary_repo, review_service, valid_draft):
    """Exporting a draft directly would bypass required approval."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")

    with pytest.raises(ReviewPolicyError):
        summary_repo.transition(
            created.summary_id,
            "EXPORTED",
            "doctor-1",
            None,
            transition_event(created.draft, "EXPORT_CLINICAL_SUMMARY"),
        )


def test_reject_requires_nonempty_reason(summary_repo, review_service, valid_draft):
    """A rejection without rationale is not reviewable by the next clinician."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")

    with pytest.raises(ReviewPolicyError):
        review_service.reject(created.summary_id, allowed_context(), "  ")


def test_export_is_only_allowed_after_approval(summary_repo, review_service, valid_draft):
    """Removing approval gating would allow a non-clinical draft to be exported."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")

    with pytest.raises(ReviewPolicyError):
        review_service.export(created.summary_id, allowed_context())

    review_service.approve(created.summary_id, allowed_context(), complete_checklist())
    assert review_service.export(created.summary_id, allowed_context()).status == "EXPORTED"


def test_review_audits_are_scope_only(summary_repo, review_service, valid_draft):
    """Adding clinical content to review audit rows would leak restricted data."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")
    review_service.reject(created.summary_id, allowed_context(), "Requires revision")

    with sqlite3.connect(summary_repo.db_path) as connection:
        row = connection.execute("SELECT * FROM audit_events").fetchone()
        columns = [column[1] for column in connection.execute("PRAGMA table_info(audit_events)")]

    assert row is not None
    assert set(columns) == {
        "user_id",
        "action",
        "subject_id",
        "hadm_id",
        "stay_id",
        "result",
        "trace_id",
        "timestamp",
    }


def test_summary_application_database_does_not_modify_clinical_source(tmp_path, valid_draft):
    """Writing review state into the source database would violate its read-only boundary."""
    source_path = tmp_path / "clinical-source.sqlite"
    application_path = tmp_path / "application.sqlite"
    create_mock_clinical_db(source_path)

    SQLiteSummaryRepository(application_path).create_draft(valid_draft, actor_id="doctor-1")

    with sqlite3.connect(source_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

    assert "summaries" not in tables
    assert "summary_versions" not in tables


def test_sqlite_summary_repository_is_disabled_in_production(monkeypatch, tmp_path):
    """Allowing local SQLite persistence in production would silently bypass PostgreSQL."""
    with monkeypatch.context() as environment:
        environment.setenv("APP_ENV", "production")
        environment.setenv("CLINICAL_BACKEND", "postgresql")
        environment.setenv("CLINICAL_POSTGRES_DSN", "postgresql://clinical")
        environment.setenv("CLINICAL_CURSOR_SECRET", "s" * 32)
        environment.setenv("SUMMARY_BACKEND", "postgresql")
        environment.setenv("SUMMARY_POSTGRES_DSN", "postgresql://summary")
        get_settings.cache_clear()
        with pytest.raises(RuntimeError, match="SQLite summary repository is disabled in production"):
            SQLiteSummaryRepository(tmp_path / "application.sqlite")
    get_settings.cache_clear()


def test_production_summary_configuration_requires_explicit_postgresql():
    """A production default of SQLite would silently select local persistence."""
    with pytest.raises(ValidationError, match="production summary backend must be explicitly set to postgresql"):
        Settings(
            app_env="production",
            clinical_backend="postgresql",
            clinical_postgres_dsn="postgresql://clinical",
            clinical_cursor_secret="s" * 32,
        )
