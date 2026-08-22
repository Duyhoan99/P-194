import io

import src.clinical.care_plan_pdf_generator as care_plan_pdf_module
import src.clinical.pdf_generator as review_pdf_module
from src.clinical.canonical import Coverage, PatientSummary, ReviewResponse
from src.clinical.care_plan_agent import CarePlanDataSummary, CarePlanDraft
from src.clinical.care_plan_pdf_generator import build_care_plan_pdf
from src.clinical.pdf_generator import generate_review_pdf


def _track_buffers(monkeypatch, module) -> list[io.BytesIO]:
    buffers: list[io.BytesIO] = []

    def buffer_factory() -> io.BytesIO:
        buffer = io.BytesIO()
        buffers.append(buffer)
        return buffer

    monkeypatch.setattr(module, "BytesIO", buffer_factory)
    return buffers


def _patient() -> PatientSummary:
    return PatientSummary(
        patient_id="PAT-001",
        pseudonym="Nguyen Demo An",
        age=61,
        sex="female",
        primary_condition="Dai thao duong tip 2",
    )


def test_review_pdf_closes_its_memory_buffer(monkeypatch) -> None:
    buffers = _track_buffers(monkeypatch, review_pdf_module)
    review = ReviewResponse(
        review_id="rev-1",
        review_version_id="rv-1",
        patient_id="PAT-001",
        status="approved",
        version=1,
        generated_at="2026-08-22T10:00:00+07:00",
        updated_at="2026-08-22T10:00:00+07:00",
        approved_at="2026-08-22T10:00:00+07:00",
        data_watermark="wm-1",
        coverage=Coverage(encounter_count=1),
        clinician_confirmation=True,
    )

    content = generate_review_pdf(review, _patient())

    assert content.startswith(b"%PDF")
    assert len(buffers) == 1
    assert buffers[0].closed


def test_care_plan_pdf_closes_its_memory_buffer(monkeypatch) -> None:
    buffers = _track_buffers(monkeypatch, care_plan_pdf_module)
    plan = CarePlanDraft(
        doctor_greeting="Loi dan cua bac si.",
        morning_meds="Theo don bac si.",
        evening_meds="Theo don bac si.",
        medication_note="Khong tu thay doi thuoc.",
        diet_good="An dung bua.",
        diet_bad="Han che duong.",
        exercise="Van dong vua suc.",
        emergency_warning="Kham ngay khi co dau hieu bat thuong.",
        follow_up="Tai kham theo lich.",
        guideline_citation="Can cu thu nghiem.",
    )

    content = build_care_plan_pdf(
        patient=_patient(),
        plan=plan,
        data_summary=CarePlanDataSummary(),
        doctor_sign_name="Bac si Demo",
    )

    assert content.startswith(b"%PDF")
    assert len(buffers) == 1
    assert buffers[0].closed
