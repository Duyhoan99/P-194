import sqlite3
from uuid import uuid4

import pytest

from src.clinical.access import DemoAssignmentProvider
from src.clinical.audit import InMemoryAuditSink
from src.clinical.errors import ClinicalAccessDenied, ReviewPolicyError
from src.clinical.review import ReviewChecklist, ReviewService
from src.clinical.schemas import AccessContext, SourceLineage
from src.clinical.summary_repository import SQLiteSummaryRepository
from src.clinical.summary_schemas import Citation, Claim, ClinicalSummaryDraft
from tests.clinical_fixtures import create_mock_clinical_db
from tests.test_clinical.conftest import TEST_TRACE_ID, allowed_context


def context_for_subject(subject_id: int) -> AccessContext:
    return AccessContext(
        user_id="doctor-1",
        role="DOCTOR",
        assigned_subject_ids={subject_id},
        trace_id=TEST_TRACE_ID,
    )


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
    )


def complete_checklist() -> ReviewChecklist:
    return ReviewChecklist(
        reviewed_summary=True,
        checked_critical_evidence=True,
        understands_ai_limitations=True,
        confirms_edits=True,
    )


def test_create_and_list_versions(summary_repo: SQLiteSummaryRepository, valid_draft: ClinicalSummaryDraft):
    """Removing durable version rows would make a created draft disappear on lookup."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")
    updated = summary_repo.update_draft(
        created.summary_id,
        actor_id="doctor-1",
        patch=valid_draft.model_copy(update={"warnings": ["Doctor requested revision."]}),
        reason="Clarify warning",
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


def test_approved_version_is_immutable(summary_repo, review_service, valid_draft):
    """Allowing an approved row to change would erase the clinician-reviewed record."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")
    review_service.approve(created.summary_id, allowed_context(), complete_checklist())

    with pytest.raises(ReviewPolicyError):
        summary_repo.update_draft(created.summary_id, "doctor-1", valid_draft, "Change approved summary")

    assert summary_repo.get(created.summary_id).status == "APPROVED"


def test_unassigned_doctor_is_denied_before_review_repository_access(summary_repo, review_service, valid_draft):
    """Checking authorization after lookup could disclose an unassigned summary."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")

    with pytest.raises(ClinicalAccessDenied):
        review_service.approve(created.summary_id, context_for_subject(102), complete_checklist())


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


def test_invalid_transition_is_rejected(summary_repo, review_service, valid_draft):
    """Exporting a draft directly would bypass required approval."""
    created = summary_repo.create_draft(valid_draft, actor_id="doctor-1")

    with pytest.raises(ReviewPolicyError):
        summary_repo.transition(created.summary_id, "EXPORTED", "doctor-1", None)


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
