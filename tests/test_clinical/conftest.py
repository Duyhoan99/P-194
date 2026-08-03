import pytest

from src.clinical.access import DemoAssignmentProvider
from src.clinical.audit import InMemoryAuditSink
from src.clinical.availability import SourceAvailability
from src.clinical.errors import ClinicalAccessDenied
from src.clinical.repository import RepositoryFetch
from src.clinical.schemas import AccessContext, ClinicalQuery, EvidenceRecord, SourceLineage

TEST_TRACE_ID = "123e4567-e89b-42d3-a456-426614174000"


def allowed_context() -> AccessContext:
    return AccessContext(
        user_id="doctor-1",
        role="DOCTOR",
        assigned_subject_ids={101},
        trace_id=TEST_TRACE_ID,
    )


class DenyAllChecker:
    def can_access(self, context: AccessContext, subject_id: int) -> bool:
        return False

    def assert_access(self, context: AccessContext, subject_id: int) -> None:
        raise ClinicalAccessDenied


class FakeRepository:
    """In-memory repository double with explicit scope and fetch behavior."""

    def __init__(self) -> None:
        self.fetch_calls: list[str] = []
        self.scope_calls = 0
        self.scope_is_valid = True
        self.fetches = {
            "fetch_patient_overview": RepositoryFetch([], []),
            "fetch_encounter_timeline": RepositoryFetch([], []),
            "fetch_diagnoses_and_procedures": RepositoryFetch([], []),
            "fetch_laboratory_results": RepositoryFetch(
                [
                    EvidenceRecord(
                        record_type="lab",
                        data={"itemid": 3001},
                        lineage=SourceLineage(
                            dataset="MIMIC-IV",
                            version="3.1",
                            module="hosp",
                            table="labevents",
                            source_row_key="labevent_id=9001",
                            subject_id=101,
                        ),
                    )
                ],
                ["d_labitems"],
            ),
            "fetch_microbiology_results": RepositoryFetch([], []),
            "fetch_icu_events": RepositoryFetch([], []),
        }

    def validate_scope(self, query: ClinicalQuery) -> bool:
        self.scope_calls += 1
        return self.scope_is_valid

    def available_sources(self) -> SourceAvailability:
        return SourceAvailability(available_tables=set(), unavailable_modules=[])

    def fetch_patient_overview(self, query: ClinicalQuery) -> RepositoryFetch:
        return self._fetch("fetch_patient_overview")

    def fetch_encounter_timeline(self, query: ClinicalQuery) -> RepositoryFetch:
        return self._fetch("fetch_encounter_timeline")

    def fetch_diagnoses_and_procedures(self, query: ClinicalQuery) -> RepositoryFetch:
        return self._fetch("fetch_diagnoses_and_procedures")

    def fetch_laboratory_results(self, query: ClinicalQuery) -> RepositoryFetch:
        return self._fetch("fetch_laboratory_results")

    def fetch_microbiology_results(self, query: ClinicalQuery) -> RepositoryFetch:
        return self._fetch("fetch_microbiology_results")

    def fetch_icu_events(self, query: ClinicalQuery) -> RepositoryFetch:
        return self._fetch("fetch_icu_events")

    def _fetch(self, name: str) -> RepositoryFetch:
        self.fetch_calls.append(name)
        outcome = self.fetches[name]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def audit_sink() -> InMemoryAuditSink:
    return InMemoryAuditSink()


@pytest.fixture
def fake_repo() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def assigned_service(fake_repo: FakeRepository, audit_sink: InMemoryAuditSink):
    from src.clinical.service import ClinicalRetrievalService

    return ClinicalRetrievalService(
        fake_repo,
        DemoAssignmentProvider({"doctor-1": {101}}, set()),
        audit_sink,
    )


@pytest.fixture
def fake_service(assigned_service):
    return assigned_service
