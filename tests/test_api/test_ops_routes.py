from fastapi.testclient import TestClient

from src.main import app


def test_ops_reports_fhir_pdf_runtime():
    with TestClient(app) as client:
        client.post("/api/v1/auth/login", json={"email": "admin-1", "password": "demo"})
        response = client.get("/api/v1/ops/clinical-status")
        assert response.status_code == 200
        body = response.json()
        assert body["data_source"] == "FHIR R4 + PDF/OCR"
        assert body["patient_count"] >= 1
        assert {"fhir", "pdf", "ocr"} <= set(body["loaded_modules"])
