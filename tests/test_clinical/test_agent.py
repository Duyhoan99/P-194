from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.clinical.errors import ClinicalAgentUnavailable, ReviewPolicyError
from src.clinical.repository import RepositoryFetch
from src.clinical.schemas import ClinicalQuery, SourceLineage
from src.clinical.summary_schemas import Citation, Claim, ClinicalSummaryDraft


class FakeStructuredLLM:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.inputs: list[object] = []

    def invoke(self, value: object) -> ClinicalSummaryDraft:
        self.inputs.append(value)
        if self.error:
            raise self.error
        return self.result


def _evidence_record():
    from src.clinical.schemas import EvidenceRecord

    return EvidenceRecord(
        record_type="lab",
        data={"label": "Creatinine", "value": "1.2", "valuenum": 1.2, "valueuom": "mg/dL"},
        lineage=SourceLineage(
            dataset="MIMIC-IV",
            version="3.1",
            module="hosp",
            table="labevents",
            source_row_key="labevent_id=9001",
            subject_id=101,
            hadm_id=5001,
            event_time=datetime(2200, 1, 10, 14, tzinfo=UTC),
        ),
    )


def _draft(citation_id: str = "labevent_id=9001") -> ClinicalSummaryDraft:
    record = _evidence_record()
    return ClinicalSummaryDraft(
        summary_id=uuid4(),
        subject_id=999,
        hadm_id=999,
        stay_id=999,
        status="APPROVED",
        sections={
            "Laboratory Trends": [
                Claim(
                    claim_id="claim-lab-1",
                    section="Laboratory Trends",
                    text="Creatinine: 1.2 mg/dL at 2200-01-10T14:00:00+00:00.",
                    citation_ids=[citation_id],
                    status="VALID",
                )
            ]
        },
        citations=[Citation(citation_id=citation_id, lineage=record.lineage, supported_fields=["valuenum", "valueuom"])],
        conflicts=[],
        limitations=[],
        trace_id="123e4567-e89b-42d3-a456-426614174000",
    )


def test_agent_retrieves_all_domains_and_returns_server_bound_draft(assigned_service, fake_repo):
    from src.clinical.agent import ClinicalAgent
    from tests.test_clinical.conftest import TEST_TRACE_ID, allowed_context

    record = _evidence_record()
    fake_repo.fetches["fetch_laboratory_results"] = RepositoryFetch([record], [])
    llm = FakeStructuredLLM(_draft())
    agent = ClinicalAgent(assigned_service, llm)

    result = agent.generate(allowed_context(), ClinicalQuery(subject_id=101, hadm_id=5001))

    assert result.subject_id == 101
    assert result.hadm_id == 5001
    assert result.stay_id is None
    assert result.status == "DRAFT"
    assert result.trace_id == TEST_TRACE_ID
    assert result.summary_id != _draft().summary_id
    assert set(fake_repo.fetch_calls) == {
        "fetch_patient_overview",
        "fetch_encounter_timeline",
        "fetch_diagnoses_and_procedures",
        "fetch_laboratory_results",
        "fetch_microbiology_results",
        "fetch_medications",
        "fetch_patient_metrics",
        "fetch_icu_events",
    }
    assert llm.inputs


def test_agent_rejects_citation_not_in_retrieved_evidence(assigned_service, fake_repo):
    from src.clinical.agent import ClinicalAgent
    from tests.test_clinical.conftest import allowed_context

    fake_repo.fetches["fetch_laboratory_results"] = RepositoryFetch([_evidence_record()], [])
    agent = ClinicalAgent(assigned_service, FakeStructuredLLM(_draft("labevent_id=missing")))

    with pytest.raises(ReviewPolicyError, match="evidence-backed"):
        agent.generate(allowed_context(), ClinicalQuery(subject_id=101))


def test_agent_fails_closed_when_llm_is_unavailable(assigned_service):
    from src.clinical.agent import ClinicalAgent
    from tests.test_clinical.conftest import allowed_context

    agent = ClinicalAgent(assigned_service, FakeStructuredLLM(error=RuntimeError("provider unavailable")))

    with pytest.raises(ClinicalAgentUnavailable, match="Structured summary generation failed"):
        agent.generate(allowed_context(), ClinicalQuery(subject_id=101))


def test_agent_returns_evidence_only_draft_when_llm_is_unavailable(assigned_service):
    from src.clinical.agent import ClinicalAgent
    from src.clinical.summary_generator import DeterministicDemoSummaryGenerator
    from tests.test_clinical.conftest import allowed_context

    agent = ClinicalAgent(
        assigned_service,
        FakeStructuredLLM(error=RuntimeError("provider unavailable")),
        fallback_generator=DeterministicDemoSummaryGenerator(),
    )

    draft = agent.generate(allowed_context(), ClinicalQuery(subject_id=101))

    assert draft.status == "DRAFT"
    assert any("evidence-only" in limitation for limitation in draft.limitations)


def test_agent_rejects_treatment_recommendation(assigned_service, fake_repo):
    from src.clinical.agent import ClinicalAgent
    from tests.test_clinical.conftest import allowed_context

    record = _evidence_record()
    fake_repo.fetches["fetch_laboratory_results"] = RepositoryFetch([record], [])
    draft = _draft()
    draft.sections["Laboratory Trends"][0].text = (
        "Start treatment: Creatinine: 1.2 mg/dL at 2200-01-10T14:00:00+00:00."
    )
    agent = ClinicalAgent(assigned_service, FakeStructuredLLM(draft))

    with pytest.raises(ReviewPolicyError, match="evidence-backed"):
        agent.generate(allowed_context(), ClinicalQuery(subject_id=101))
