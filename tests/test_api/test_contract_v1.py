"""Contract tests for API_CONTRACT.md compliance."""

import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_auth_login_and_me():
    response = client.post("/api/v1/auth/login", json={"email": "doctor@example.test", "password": "demo-password"})
    assert response.status_code == 200
    user = response.json()
    assert user["user_id"] == "usr_doctor_demo"
    assert "clinician" in user["roles"]

    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["user_id"] == "usr_doctor_demo"


def test_list_patients():
    response = client.get("/api/v1/patients")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 6
    patient_ids = [p["patient_id"] for p in data["items"]]
    assert "PAT-001" in patient_ids


def test_patient_timeline():
    response = client.get("/api/v1/patients/PAT-001/timeline")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "data_watermark" in data
    assert len(data["items"]) > 0


def test_patient_trends_with_provenance():
    response = client.get("/api/v1/patients/PAT-001/trends?code=4548-4")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "4548-4"
    assert data["display"] == "HbA1c"
    assert "points" in data
    assert len(data["points"]) > 0
    first_pt = data["points"][0]
    assert "value" in first_pt
    assert "unit" in first_pt
    assert "calculation" in first_pt


def test_patient_scope_denial_unknown_patient():
    response = client.get("/api/v1/patients/PAT-99999/timeline")
    assert response.status_code == 404
    err = response.json()["detail"]
    assert err["code"] == "PATIENT_SCOPE_DENIED"


def test_review_lifecycle_generate_edit_approve_memory_export():
    # 1. Generate Review
    gen_resp = client.post("/api/v1/patients/PAT-001/reviews/generate", json={"profile_versions": ["type_2_diabetes@1.0.0"]})
    assert gen_resp.status_code == 201
    rev = gen_resp.json()
    review_id = rev["review_id"]
    rv_id = rev["review_version_id"]
    assert rev["version"] == 1
    assert rev["status"] == "generated"

    # 2. Export PDF before approval should fail
    exp_fail = client.get(f"/api/v1/reviews/{review_id}/export.pdf?review_version_id={rv_id}")
    assert exp_fail.status_code == 409
    assert exp_fail.json()["detail"]["code"] == "EXPORT_NOT_ALLOWED"

    # 3. Patch Review (Edit)
    patch_resp = client.patch(
        f"/api/v1/reviews/{review_id}",
        json={
            "expected_version": 1,
            "sections": [{"section_code": "patient_overview", "clinician_text": "Bác sĩ đã kiểm tra và xác nhận."}],
            "edit_reason": "Bổ sung nhận định",
        },
    )
    assert patch_resp.status_code == 200
    patched_rev = patch_resp.json()
    assert patched_rev["version"] == 2
    assert patched_rev["status"] == "edited"
    new_rv_id = patched_rev["review_version_id"]

    # 4. Approve without confirmation should fail
    app_fail = client.post(
        f"/api/v1/reviews/{review_id}/approve",
        json={"review_version_id": new_rv_id, "expected_version": 2, "clinician_confirmation": False},
    )
    assert app_fail.status_code == 409
    assert app_fail.json()["detail"]["code"] == "CONFIRMATION_REQUIRED"

    # 5. Approve with confirmation
    app_success = client.post(
        f"/api/v1/reviews/{review_id}/approve",
        json={"review_version_id": new_rv_id, "expected_version": 2, "clinician_confirmation": True},
    )
    assert app_success.status_code == 200
    approved_rev = app_success.json()
    assert approved_rev["status"] == "approved"
    assert approved_rev["approved_at"] is not None

    # 6. Memory should now be available
    mem_resp = client.get("/api/v1/patients/PAT-001/memory")
    assert mem_resp.status_code == 200
    mem = mem_resp.json()
    assert mem["patient_id"] == "PAT-001"
    assert len(mem["items"]) > 0

    # 7. Export PDF after approval should succeed
    exp_success = client.get(f"/api/v1/reviews/{review_id}/export.pdf?review_version_id={new_rv_id}")
    assert exp_success.status_code == 200
    assert exp_success.headers["content-type"] == "application/pdf"
    assert "attachment" in exp_success.headers["content-disposition"]


def test_ocr_verification_workflow():
    list_resp = client.get("/api/v1/patients/PAT-003/verification-items")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    if items:
        item_id = items[0]["verification_item_id"]
        patch_resp = client.patch(
            f"/api/v1/verification-items/{item_id}",
            json={"decision": "verified", "corrected_text": "HbA1c 8,7%", "expected_version": 1},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["status"] == "verified"
        assert patch_resp.json()["corrected_text"] == "HbA1c 8,7%"
