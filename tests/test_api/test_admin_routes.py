from fastapi.testclient import TestClient

from src.main import app


def test_admin_assigns_fhir_patient_id_to_doctor():
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"email": "admin-1", "password": "demo"})
        assert login.status_code == 200

        assigned = client.post(
            "/api/v1/admin/users/doctor-2/assignments",
            json={"patient_id": "PAT-001"},
        )
        assert assigned.status_code == 200
        assert "PAT-001" in assigned.json()["assignments"]

        revoked = client.delete("/api/v1/admin/users/doctor-2/assignments/PAT-001")
        assert revoked.status_code == 200
        assert "PAT-001" not in revoked.json()["assignments"]


def test_doctor_cannot_manage_assignments():
    with TestClient(app) as client:
        client.post("/api/v1/auth/login", json={"email": "doctor-1", "password": "demo"})
        response = client.post(
            "/api/v1/admin/users/doctor-2/assignments",
            json={"patient_id": "PAT-001"},
        )
        assert response.status_code == 403
