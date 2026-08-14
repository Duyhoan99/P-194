"""Runtime E2E: one patient, three independent clinical source documents."""

from __future__ import annotations

import io
import json
from unittest import mock

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from reportlab.pdfgen import canvas

from src.api import ingestion_routes
from src.api.dependencies import get_demo_repository
from src.clinical.demo_repository import DemoRepository
from src.clinical.fhir_canonicalizer import canonicalize_fhir_bundle
from src.clinical.pdf_extractor import MockOcrExtractor
from src.config import get_settings
from src.main import app


def _text_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 760, text)
    pdf.save()
    return buffer.getvalue()


def _scan_pdf() -> bytes:
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(buffer)
    return buffer.getvalue()


def _documents(body: dict) -> set[str]:
    return {citation["document_id"] for citation in body["citations"]}


def test_uploaded_fhir_text_pdf_and_ocr_merge_and_answer(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "deterministic")
    monkeypatch.setenv("AGENT_GENERATION_BACKEND", "deterministic")
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()
    repo = DemoRepository()
    patient_id = "PAT-900"
    repo.create_blank_patient(patient_id, "Multi Source Patient")
    repo.create_blank_patient("PAT-901", "Isolation Control")
    app.dependency_overrides[get_demo_repository] = lambda: repo
    fhir_bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {
                "resourceType": "Condition", "id": "cond-ms-1",
                "subject": {"reference": f"Patient/{patient_id}"},
                "recordedDate": "2026-07-01T08:00:00+07:00",
                "code": {"coding": [{"code": "44054006", "display": "Type 2 diabetes"}]},
            }},
            {"resource": {
                "resourceType": "Observation", "id": "obs-ms-1", "status": "final",
                "subject": {"reference": f"Patient/{patient_id}"},
                "effectiveDateTime": "2026-07-01T08:05:00+07:00",
                "code": {"text": "Baseline potassium"},
                "valueQuantity": {"value": 4.2, "unit": "mmol/L"},
            }},
        ],
    }
    original_ocr = ingestion_routes._gemini_ocr_extractor
    ingestion_routes._gemini_ocr_extractor = MockOcrExtractor(
        mock_text="Medication narrative: evening vitamin D dose is often missed.",
        confidence=0.96,
    )
    try:
        with mock.patch("src.agents.retrieval.vector.index_evidence") as index_mock:
            with TestClient(app) as client:
                fhir_response = client.post(
                    "/api/v1/ingestions", data={"patient_id": patient_id, "format": "fhir_r4"},
                    files={"file": ("bundle.json", json.dumps(fhir_bundle).encode(), "application/json")},
                )
                text_response = client.post(
                    "/api/v1/ingestions", data={"patient_id": patient_id},
                    files={"file": ("allergy-note.pdf", _text_pdf("Allergy note: Penicillin causes rash."), "application/pdf")},
                )
                ocr_response = client.post(
                    "/api/v1/ingestions", data={"patient_id": patient_id},
                    files={"file": ("scan.pdf", _scan_pdf(), "application/pdf")},
                )
                other_response = client.post(
                    "/api/v1/ingestions", data={"patient_id": "PAT-901"},
                    files={"file": ("private.pdf", _text_pdf("Isolation secret clinical fact."), "application/pdf")},
                )
                assert fhir_response.json()["status"] == "completed"
                assert text_response.json()["status"] == "completed"
                assert ocr_response.json()["status"] == "completed"
                assert other_response.json()["status"] == "completed"

                fhir_doc = fhir_response.json()["source_document_id"]
                text_doc = text_response.json()["source_document_id"]
                ocr_doc = ocr_response.json()["source_document_id"]
                packet = repo.build_evidence_packet(patient_id)
                assert len(packet.fhir_evidence) == 2
                assert sum(e["source_value"].get("source_type") == "text_layer" for e in packet.pdf_evidence) == 1
                assert sum(e["source_value"].get("source_type") == "ocr" for e in packet.pdf_evidence) == 1
                packet_docs = {
                    citation["document_id"]
                    for item in packet.fhir_evidence + packet.pdf_evidence
                    for citation in item["citations"]
                }
                assert packet_docs == {fhir_doc, text_doc, ocr_doc}
                assert index_mock.call_count == 3  # two patient PDFs plus isolation-control PDF

                summary = client.post(
                    f"/api/v1/patients/{patient_id}/ask",
                    json={"question": "Tóm tắt các dữ kiện lâm sàng đang có trong hồ sơ."},
                ).json()
                assert summary["status"] == "answered"
                assert {fhir_doc, text_doc, ocr_doc} <= _documents(summary), summary
                assert "Isolation secret" not in summary["answer"]

                diagnosis = client.post(
                    f"/api/v1/patients/{patient_id}/ask",
                    json={"question": "Chẩn đoán nào đang được ghi nhận?"},
                ).json()
                assert diagnosis["status"] == "answered" and _documents(diagnosis) == {fhir_doc}

                text_fact = client.post(
                    f"/api/v1/patients/{patient_id}/ask",
                    json={"question": "Ghi chú có nói gì về Penicillin?"},
                ).json()
                assert text_fact["status"] == "answered" and text_doc in _documents(text_fact)
                assert "Penicillin causes rash" in text_fact["answer"]

                ocr_fact = client.post(
                    f"/api/v1/patients/{patient_id}/ask",
                    json={"question": "Ghi chú nói gì về liều vitamin D buổi tối?"},
                ).json()
                assert ocr_fact["status"] == "answered" and ocr_doc in _documents(ocr_fact)
                assert "vitamin D dose is often missed" in ocr_fact["answer"]
    finally:
        ingestion_routes._gemini_ocr_extractor = original_ocr
        app.dependency_overrides.pop(get_demo_repository, None)
        get_settings.cache_clear()


def test_zero_evidence_ocr_is_completed_with_warning(monkeypatch):
    repo = DemoRepository()
    app.dependency_overrides[get_demo_repository] = lambda: repo
    original_ocr = ingestion_routes._gemini_ocr_extractor
    ingestion_routes._gemini_ocr_extractor = MockOcrExtractor(mock_text="", confidence=0.0)
    try:
        with mock.patch("src.agents.retrieval.vector.index_evidence"):
            response = TestClient(app).post(
                "/api/v1/ingestions", data={"patient_id": "PAT-001"},
                files={"file": ("empty-scan.pdf", _scan_pdf(), "application/pdf")},
            )
        body = response.json()
        assert body["status"] == "completed_with_warnings"
        assert body["counts"]["accepted"] == 0
        assert body["errors"][0]["code"] == "NO_EVIDENCE_EXTRACTED"
    finally:
        ingestion_routes._gemini_ocr_extractor = original_ocr
        app.dependency_overrides.pop(get_demo_repository, None)


def test_fhir_upload_rejects_cross_patient_reference():
    repo = DemoRepository()
    app.dependency_overrides[get_demo_repository] = lambda: repo
    bundle = {
        "resourceType": "Bundle", "type": "collection",
        "entry": [{"resource": {
            "resourceType": "Condition", "id": "foreign-condition",
            "subject": {"reference": "Patient/PAT-002"},
            "code": {"text": "Foreign condition"},
        }}],
    }
    try:
        response = TestClient(app).post(
            "/api/v1/ingestions", data={"patient_id": "PAT-001", "format": "fhir_r4"},
            files={"file": ("foreign.json", json.dumps(bundle).encode(), "application/json")},
        )
        assert response.status_code == 202
        assert response.json()["status"] == "failed"
        assert response.json()["errors"][0]["code"] == "FHIR_VALIDATION_FAILED"
        assert repo.build_evidence_packet("PAT-001").fhir_evidence == []
    finally:
        app.dependency_overrides.pop(get_demo_repository, None)


def test_fhir_canonicalizer_supports_required_resource_types():
    patient_id = "PAT-900"
    common = {"subject": {"reference": f"Patient/{patient_id}"}}
    bundle = {
        "resourceType": "Bundle", "type": "collection", "entry": [
            {"resource": {**common, "resourceType": "Condition", "id": "c1",
                          "recordedDate": "2026-01-01", "code": {"text": "Condition A"}}},
            {"resource": {**common, "resourceType": "Observation", "id": "o1", "status": "final",
                          "effectiveDateTime": "2026-01-02", "code": {"text": "Test A"},
                          "valueQuantity": {"value": 1, "unit": "mg/L"}}},
            {"resource": {**common, "resourceType": "Encounter", "id": "e1", "status": "finished",
                          "period": {"start": "2026-01-03"}}},
            {"resource": {**common, "resourceType": "MedicationRequest", "id": "mr1", "status": "active",
                          "authoredOn": "2026-01-04", "medicationCodeableConcept": {"text": "Drug A"}}},
            {"resource": {**common, "resourceType": "MedicationStatement", "id": "ms1", "status": "active",
                          "dateAsserted": "2026-01-05", "medicationCodeableConcept": {"text": "Drug B"}}},
        ],
    }
    evidence = canonicalize_fhir_bundle(
        bundle, patient_id=patient_id, tenant_id="ten_demo",
        document_id="doc_fhir_required", source_checksum="sha256:test",
    )
    assert len(evidence) == 5
    assert {item["fact_type"] for item in evidence} == {
        "timeline_condition", "timeline_observation", "timeline_encounter", "timeline_medication",
    }
    assert all(item["patient_id"] == patient_id and item["tenant_id"] == "ten_demo" for item in evidence)
    assert all(item["source_time"] and item["citations"][0]["document_id"] == "doc_fhir_required" for item in evidence)
