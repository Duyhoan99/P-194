"""Regression tests for the printable approved clinical summary."""

from io import BytesIO

from pypdf import PdfReader

from src.clinical.canonical import (
    ConflictFlag,
    Coverage,
    DataQualityFlag,
    DocumentCitation,
    DrugInteractionFlag,
    PatientSummary,
    ReviewResponse,
    ReviewSection,
    VerifiedClaim,
)
from src.clinical.pdf_generator import generate_review_pdf


def _approved_review() -> tuple[ReviewResponse, PatientSummary]:
    citation = DocumentCitation(
        citation_id="cit-secret-001",
        document_id="doc-secret-001",
        document_name="tai_lieu_nguon_khong_duoc_in.pdf",
        page_number=4,
        snippet="Đoạn trích nguồn không được xuất hiện trong bản PDF.",
        source_checksum="sha256:test",
    )
    review = ReviewResponse(
        review_id="rev_PAT-001",
        review_version_id="rv_PAT-001_v2",
        patient_id="PAT-001",
        status="approved",
        version=2,
        generated_at="2026-08-20T09:00:00+07:00",
        updated_at="2026-08-22T10:15:00+07:00",
        approved_at="2026-08-22T10:15:00+07:00",
        data_watermark="wm_PAT-001_v2",
        coverage=Coverage(start_date="2025-01-05", end_date="2026-01-05", encounter_count=3),
        sections=[
            ReviewSection(
                section_code="patient_overview",
                title="Tổng quan",
                clinician_text="Bệnh nhân tỉnh, hợp tác tốt và tuân thủ điều trị.",
                claims=[
                    VerifiedClaim(
                        claim_id="claim-001",
                        text="Tái khám định kỳ, tình trạng lâm sàng ổn định.",
                        status="verified",
                        citations=[citation],
                    )
                ],
            ),
            ReviewSection(
                section_code="current_medications",
                title="Thuốc",
                claims=[
                    VerifiedClaim(
                        claim_id="claim-002",
                        text="Metformin 500 mg đang duy trì theo đơn hiện tại.",
                        status="verified",
                        citations=[citation],
                    )
                ],
            ),
        ],
        conflicts=[
            ConflictFlag(
                conflict_id="conflict-001",
                conflict_type="medication_dose",
                description="Cần xác nhận lại liều dùng trong lần tái khám kế tiếp.",
                status="reviewed",
                source_a=[citation],
                source_b=[citation],
            )
        ],
        drug_interactions=[
            DrugInteractionFlag(
                flag_id="interaction-001",
                ingredients=["metformin"],
                severity="moderate",
                description="Theo dõi chức năng thận định kỳ.",
                rule_source="test-rule",
                rule_version="1.0",
                status="reviewed",
                citations=[citation],
            )
        ],
        data_quality_flags=[
            DataQualityFlag(
                flag_id="quality-001",
                code="FOLLOW_UP",
                severity="warning",
                message="Cần bổ sung kết quả xét nghiệm ở lần tái khám tiếp theo.",
                status="open",
            )
        ],
        clinician_confirmation=True,
    )
    patient = PatientSummary(
        patient_id="PAT-001",
        pseudonym="Nguyễn Demo An",
        age=61,
        sex="female",
        primary_condition="Đái tháo đường type 2",
        last_encounter_at="2026-01-05",
        latest_data_watermark="wm_PAT-001_v2",
    )
    return review, patient


def test_pdf_is_readable_complete_and_excludes_source_citations():
    review, patient = _approved_review()
    content = generate_review_pdf(review, patient)

    assert content.startswith(b"%PDF")
    reader = PdfReader(BytesIO(content))
    assert len(reader.pages) >= 1
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "BẢN TÓM TẮT ĐIỀU TRỊ" in text
    assert "Nguyễn Demo An" in text
    assert "Thuốc và phác đồ điều trị" in text
    assert "Metformin 500 mg" in text
    assert "CẢNH BÁO VÀ ĐIỂM CẦN LƯU Ý" in text
    assert "mức trung bình" in text
    assert "moderate" not in text
    assert "ĐÃ PHÊ DUYỆT" in text

    assert "cit-secret-001" not in text
    assert "tai_lieu_nguon_khong_duoc_in.pdf" not in text
    assert "Đoạn trích nguồn không được xuất hiện" not in text
    assert "Nguồn bằng chứng" not in text
