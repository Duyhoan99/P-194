from copy import deepcopy

import pytest

from src.clinical.claim_validator import ClaimValidator
from src.clinical.errors import ClinicalAccessDenied, ClinicalQueryTimeout
from src.clinical.repository import RepositoryFetch
from src.clinical.schemas import AccessContext, ClinicalQuery, EvidenceRecord, SourceLineage
from src.clinical.service import ClinicalRetrievalService
from src.clinical.summary_generator import DeterministicDemoSummaryGenerator
from src.clinical.summary_schemas import Citation
from src.clinical.summary_service import ClinicalSummaryService
from src.config import get_settings


def test_validator_rejects_claim_without_citation(evidence, draft_with_claim):
    """Removing the citation requirement would allow unsupported claims."""
    draft = draft_with_claim(text="Creatinine is 1.2", citation_ids=[])

    report = ClaimValidator().validate(draft, evidence)

    assert report.valid is False
    assert report.errors[0].code == "MISSING_CITATION"


def test_demo_generator_preserves_lab_value_and_lineage(evidence, first_claim):
    """Dropping evidence formatting or lineage would hide the source for a lab claim."""
    draft = DeterministicDemoSummaryGenerator().generate(evidence)
    claim = first_claim(draft, section="Laboratory Trends")

    assert "1.2 mg/dL" in claim.text
    assert "2200-01-10T14:00:00+00:00" in claim.text
    assert claim.citation_ids == ["labevent_id=9001"]
    assert draft.citations[0].lineage.table == "labevents"


def test_validator_rejects_citation_for_missing_source(evidence, draft_with_claim):
    """Accepting an unknown evidence key would allow fabricated provenance."""
    draft = draft_with_claim(text="Creatinine is 1.2 mg/dL", citation_ids=["labevent_id=missing"])

    report = ClaimValidator().validate(draft, evidence)

    assert report.valid is False
    assert report.errors[0].code == "MISSING_SOURCE"


def test_validator_rejects_mismatched_numeric_value(evidence, draft_with_claim):
    """Accepting a changed numeric result would allow a materially incorrect clinical claim."""
    draft = draft_with_claim(text="Creatinine is 2.0 mg/dL", citation_ids=["labevent_id=9001"])
    draft.citations = [
        Citation(
            citation_id="labevent_id=9001",
            lineage=evidence[0].lineage,
            supported_fields=["value", "valueuom"],
        )
    ]

    report = ClaimValidator().validate(draft, evidence)

    assert report.valid is False
    assert report.errors[0].code == "NUMERIC_VALUE_MISMATCH"


def test_validator_rejects_lab_claim_with_mismatched_timestamp(evidence, draft_with_claim):
    """Dropping an evidence timestamp would allow a claim to misstate when a result occurred."""
    draft = draft_with_claim(
        text="Creatinine is 1.2 mg/dL at 2200-01-10T15:00:00+00:00",
        citation_ids=["labevent_id=9001"],
    )
    draft.citations = [
        Citation(
            citation_id="labevent_id=9001",
            lineage=evidence[0].lineage,
            supported_fields=["value", "valueuom"],
        )
    ]

    report = ClaimValidator().validate(draft, evidence)

    assert report.valid is False
    assert report.errors[0].code == "TIMESTAMP_MISMATCH"


def test_validator_accepts_integer_lab_value_with_matching_unit_and_timestamp(evidence, draft_with_claim):
    """Decimal-only parsing would incorrectly reject an evidence-backed integer result."""
    integer_evidence = [
        evidence[0].model_copy(
            update={"data": {"label": "Potassium", "value": "4", "valuenum": 4, "valueuom": "mmol/L"}}
        )
    ]
    timestamp = integer_evidence[0].lineage.event_time.isoformat()
    draft = draft_with_claim(text=f"Potassium is 4 mmol/L at {timestamp}", citation_ids=["labevent_id=9001"])
    draft.citations = [
        Citation(
            citation_id="labevent_id=9001",
            lineage=integer_evidence[0].lineage,
            supported_fields=["value", "valueuom"],
        )
    ]

    report = ClaimValidator().validate(draft, integer_evidence)

    assert report.valid is True


def test_validator_rejects_non_lab_claim_without_supported_evidence_values(draft_with_claim):
    """Accepting arbitrary prose with a real citation would permit unsupported clinical claims."""
    record = EvidenceRecord(
        record_type="diagnosis",
        data={"diagnosis": "Synthetic diagnosis"},
        lineage=SourceLineage(
            dataset="MIMIC-IV",
            version="3.1",
            module="hosp",
            table="diagnoses_icd",
            source_row_key="diagnosis_id=1",
            subject_id=101,
        ),
    )
    draft = draft_with_claim(text="The patient is clinically stable.", citation_ids=["diagnosis_id=1"])
    draft.citations = [
        Citation(
            citation_id="diagnosis_id=1",
            lineage=record.lineage,
            supported_fields=["diagnosis"],
        )
    ]

    report = ClaimValidator().validate(draft, [record])

    assert report.valid is False
    assert report.errors[0].code == "UNSUPPORTED_CLAIM"


def test_validator_rejects_mismatched_lineage(evidence, draft_with_claim):
    """Accepting altered lineage would disconnect the claim from the cited source row."""
    draft = draft_with_claim(text="Creatinine is 1.2 mg/dL", citation_ids=["labevent_id=9001"])
    mismatched_lineage = deepcopy(evidence[0].lineage)
    mismatched_lineage.table = "microbiologyevents"
    draft.citations = [
        Citation(
            citation_id="labevent_id=9001",
            lineage=mismatched_lineage,
            supported_fields=["value", "valueuom"],
        )
    ]

    report = ClaimValidator().validate(draft, evidence)

    assert report.valid is False
    assert report.errors[0].code == "LINEAGE_MISMATCH"


def test_validator_rejects_unavailable_source_table(evidence, draft_with_claim):
    """Accepting a table outside the source allow-list would make provenance unverifiable."""
    unavailable_lineage = evidence[0].lineage.model_copy(update={"table": "unavailable_table"})
    unavailable_evidence = [evidence[0].model_copy(update={"lineage": unavailable_lineage})]
    draft = draft_with_claim(text="Creatinine is 1.2 mg/dL", citation_ids=["labevent_id=9001"])
    draft.citations = [
        Citation(
            citation_id="labevent_id=9001",
            lineage=unavailable_lineage,
            supported_fields=["value", "valueuom"],
        )
    ]

    report = ClaimValidator().validate(draft, unavailable_evidence)

    assert report.valid is False
    assert report.errors[0].code == "UNAVAILABLE_SOURCE"


def test_demo_generator_marks_conflicting_medications_unresolved(evidence):
    """Automatically resolving competing medication values would conceal a clinical conflict."""
    conflicting_evidence = evidence + [
        EvidenceRecord(
            record_type="medication",
            data={"medication": "metoprolol", "dose": "25 mg"},
            lineage=SourceLineage(
                dataset="MIMIC-IV",
                version="3.1",
                module="hosp",
                table="chartevents",
                source_row_key="prescription_id=1",
                subject_id=101,
            ),
        ),
        EvidenceRecord(
            record_type="medication",
            data={"medication": "metoprolol", "dose": "50 mg"},
            lineage=SourceLineage(
                dataset="MIMIC-IV",
                version="3.1",
                module="hosp",
                table="chartevents",
                source_row_key="prescription_id=2",
                subject_id=101,
            ),
        ),
    ]

    draft = DeterministicDemoSummaryGenerator().generate(conflicting_evidence)

    assert draft.conflicts[0].status == "UNRESOLVED"
    assert draft.conflicts[0].evidence_ids == ["prescription_id=1", "prescription_id=2"]


def test_demo_generator_handles_empty_evidence_with_limitations():
    """Returning a fabricated claim for an empty retrieval would break evidence-first behavior."""
    draft = DeterministicDemoSummaryGenerator().generate([])

    assert all(not claims for claims in draft.sections.values())
    assert "No clinical evidence was available for summary generation." in draft.limitations


def test_demo_generator_is_disabled_in_production(monkeypatch):
    """Allowing the deterministic provider in production would violate its demo-only boundary."""
    with monkeypatch.context() as environment:
        environment.setenv("APP_ENV", "production")
        environment.setenv("CLINICAL_BACKEND", "postgresql")
        environment.setenv("CLINICAL_POSTGRES_DSN", "postgresql://example")
        environment.setenv("CLINICAL_CURSOR_SECRET", "s" * 32)
        environment.setenv("SUMMARY_BACKEND", "postgresql")
        environment.setenv("SUMMARY_POSTGRES_DSN", "postgresql://summary")
        get_settings.cache_clear()
        with pytest.raises(RuntimeError, match="demo summary generator is disabled in production"):
            DeterministicDemoSummaryGenerator().generate([])
    get_settings.cache_clear()


def test_summary_service_retrieves_authorized_evidence_before_generation(
    assigned_service, audit_sink, fake_repo
):
    """Bypassing retrieval would allow the generator to run without server-side authorization."""
    context = AccessContext(
        user_id="doctor-1",
        role="DOCTOR",
        assigned_subject_ids={101},
        trace_id="123e4567-e89b-42d3-a456-426614174000",
    )
    draft = ClinicalSummaryService(assigned_service, audit_sink=audit_sink).generate(
        context, query=ClinicalQuery(subject_id=101)
    )

    assert fake_repo.fetch_calls == [
        "fetch_patient_overview",
        "fetch_encounter_timeline",
        "fetch_diagnoses_and_procedures",
        "fetch_laboratory_results",
        "fetch_microbiology_results",
        "fetch_icu_events",
    ]
    assert draft.subject_id == 101


def test_summary_service_fails_closed_and_audits_denied_generation(fake_repo, audit_sink):
    """Generating after a denied retrieval would expose a draft for an unassigned patient."""
    from tests.test_clinical.conftest import DenyAllChecker

    retrieval = ClinicalRetrievalService(
        fake_repo,
        DenyAllChecker(),
        audit_sink,
        cursor_secret="s" * 32,
    )
    context = AccessContext(
        user_id="doctor-1",
        role="DOCTOR",
        assigned_subject_ids=set(),
        trace_id="123e4567-e89b-42d3-a456-426614174000",
    )

    with pytest.raises(ClinicalAccessDenied):
        ClinicalSummaryService(retrieval, audit_sink=audit_sink).generate(context, ClinicalQuery(subject_id=101))

    event = audit_sink.events[-1]
    assert event.action == "GENERATE_CLINICAL_SUMMARY"
    assert event.result == "DENIED"
    assert set(event.model_dump()) == {
        "user_id",
        "action",
        "subject_id",
        "hadm_id",
        "stay_id",
        "result",
        "trace_id",
        "timestamp",
    }


def test_summary_service_preserves_partial_source_metadata_and_audits_generation(
    assigned_service, audit_sink
):
    """Discarding a partial retrieval warning would make unavailable sources invisible to reviewers."""
    context = AccessContext(
        user_id="doctor-1",
        role="DOCTOR",
        assigned_subject_ids={101},
        trace_id="123e4567-e89b-42d3-a456-426614174000",
    )

    draft = ClinicalSummaryService(assigned_service, audit_sink=audit_sink).generate(
        context, ClinicalQuery(subject_id=101)
    )

    assert draft.warnings == ["Clinical source unavailable: d_labitems"]
    assert "One or more requested clinical sources are unavailable." in draft.limitations
    assert audit_sink.events[-1].action == "GENERATE_CLINICAL_SUMMARY"
    assert audit_sink.events[-1].result == "PARTIAL"


def test_summary_service_preserves_not_loaded_source_metadata(assigned_service, fake_repo, audit_sink):
    """An unavailable source with no rows must remain visible rather than becoming an ordinary empty draft."""
    fake_repo.fetches["fetch_laboratory_results"] = RepositoryFetch([], ["labevents"])
    context = AccessContext(
        user_id="doctor-1",
        role="DOCTOR",
        assigned_subject_ids={101},
        trace_id="123e4567-e89b-42d3-a456-426614174000",
    )

    draft = ClinicalSummaryService(assigned_service, audit_sink=audit_sink).generate(
        context, ClinicalQuery(subject_id=101)
    )

    assert draft.warnings == ["Clinical source unavailable: labevents"]
    assert "One or more requested clinical sources are unavailable." in draft.limitations
    assert audit_sink.events[-1].result == "NOT_LOADED"


def test_summary_service_audits_retrieval_errors(assigned_service, fake_repo, audit_sink):
    """An unrecorded retrieval error would leave a summary-generation attempt untraceable."""
    fake_repo.fetches["fetch_patient_overview"] = ClinicalQueryTimeout()
    context = AccessContext(
        user_id="doctor-1",
        role="DOCTOR",
        assigned_subject_ids={101},
        trace_id="123e4567-e89b-42d3-a456-426614174000",
    )

    with pytest.raises(ClinicalQueryTimeout):
        ClinicalSummaryService(assigned_service, audit_sink=audit_sink).generate(
            context, ClinicalQuery(subject_id=101)
        )

    assert audit_sink.events[-1].action == "GENERATE_CLINICAL_SUMMARY"
    assert audit_sink.events[-1].result == "ERROR"
