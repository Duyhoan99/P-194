import pytest

from src.api.dependencies import get_demo_repository


@pytest.mark.anyio
async def test_optional_review_lookup_returns_empty_without_404(client) -> None:
    repo = get_demo_repository()
    patient_id = "PAT-OPTIONAL-REVIEW"
    repo.create_blank_patient(patient_id, "Bệnh nhân chưa có review")
    try:
        required_response = await client.get(f"/api/v1/patients/{patient_id}/review")
        assert required_response.status_code == 404
        assert required_response.json()["detail"]["code"] == "RESOURCE_NOT_FOUND"

        response = await client.get(
            f"/api/v1/patients/{patient_id}/review",
            params={"allow_missing": "true"},
        )
        assert response.status_code == 204
        assert response.content == b""
    finally:
        repo.delete_patient(patient_id)
