"""Test for smart document extraction, markdown conversion, patient matching, and clinical entity ingestion."""

import io
from unittest import mock
from fastapi.testclient import TestClient

from src.api.dependencies import get_demo_repository
from src.clinical.demo_repository import DemoRepository
from src.clinical.pdf_extractor import (
    BlockExtraction,
    DocumentExtraction,
    PageExtraction,
)
from src.main import app


def test_smart_document_ingestion_and_patient_resolution():
    """Verify that uploading a document without explicit patient_id:
    1. Parses document text to identify patient 'PAT-001' (Nguyễn Demo An).
    2. Updates PAT-001 rather than creating a new random patient.
    3. Adds HbA1c 7.3% and Glucose 8.2 mmol/L to trends and timeline on 2026-08-17.
    """
    repo = DemoRepository()
    app.dependency_overrides[get_demo_repository] = lambda: repo
    client = TestClient(app)

    try:
        sample_doc_md = """# PHIẾU KẾT QUẢ XÉT NGHIỆM
Mã tài liệu: DOC-PAT001-LAB-002
Mã bệnh nhân: PAT-001
Tên synthetic: Nguyễn Demo An
Ngày sinh / Giới tính: 1965-04-12 / Nữ
Ngày tài liệu: 2026-08-17

## CHẨN ĐOÁN
- Đái tháo đường type 2 (44054006)
- Tăng huyết áp (38341003)

## KẾT QUẢ XÉT NGHIỆM
| Xét nghiệm | Kết quả | Đơn vị | Tham chiếu | Cờ |
| HbA1c | 7.3 | % | 4.0 - 6.0 | H |
| Glucose | 8.2 | mmol/L | 3.9 - 6.4 | H |
| Creatinine | 88 | µmol/L | 45 - 90 | |
| eGFR | 72 | mL/min/1.73m2 | >= 90 | L |
| Systolic BP | 138 | mmHg | < 130 | H |
| Diastolic BP | 86 | mmHg | < 80 | H |
"""

        mock_extraction = DocumentExtraction(
            document_id="DOC-PAT001-LAB-002",
            page_count=1,
            pages=[
                PageExtraction(
                    page_number=1,
                    full_text=sample_doc_md,
                    blocks=[
                        BlockExtraction(
                            page_number=1,
                            block_id="blk_0",
                            text=sample_doc_md,
                            source_type="ocr",
                            ocr_confidence=0.98,
                        )
                    ],
                    has_text_layer=False,
                )
            ],
            source_checksum="sha256:mocklab002",
            has_text_layer=False,
        )

        with mock.patch("src.api.ingestion_routes._get_vision_extractor") as mock_extractor_factory, \
             mock.patch("src.agents.retrieval.vector.index_evidence"):
            mock_extractor = mock.MagicMock()
            mock_extractor.extract.return_value = mock_extraction
            mock_extractor_factory.return_value = mock_extractor

            # Upload without patient_id parameter
            response = client.post(
                "/api/v1/ingestions",
                files={"file": ("lab_result_20260817.png", io.BytesIO(b"\x89PNG\r\n\x1a\n\x00fakeimage"), "image/png")},
            )

            assert response.status_code == 202, f"Upload failed: {response.text}"
            body = response.json()
            assert body["status"] in {"completed", "completed_with_warnings"}
            # Resolved patient MUST be PAT-001
            assert body["patient_id"] == "PAT-001"

            # Check Trends for HbA1c
            display, unit, hba1c_points = repo.get_trends("PAT-001", "4548-4")
            assert any("7.3" in str(p.value) and "2026-08-17" in p.observed_at for p in hba1c_points)

            # Check Trends for Glucose
            display, unit, glucose_points = repo.get_trends("PAT-001", "2339-0")
            assert any("8.2" in str(p.value) and "2026-08-17" in p.observed_at for p in glucose_points)

            # Check Timeline
            timeline_events = repo.get_timeline("PAT-001")
            assert any("2026-08-17" in evt.occurred_at for evt in timeline_events)

            # Check Evidence Packet
            packet = repo.build_evidence_packet("PAT-001")
            assert len(packet.pdf_evidence) > 0

    finally:
        app.dependency_overrides.pop(get_demo_repository, None)
