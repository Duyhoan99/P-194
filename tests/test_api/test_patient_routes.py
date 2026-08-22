import pytest


@pytest.mark.anyio
async def test_delete_patient(client):
    from src.api.dependencies import get_demo_repository
    from src.clinical.operations import operational_store
    repo = get_demo_repository()

    patient_id = "PAT-DELETE-TEST"
    repo.create_blank_patient(patient_id, "Test Patient")

    assert repo.get_patient(patient_id) is not None

    response = await client.delete(f"/api/v1/patients/{patient_id}")
    assert response.status_code == 204

    assert repo.get_patient(patient_id) is None

    response2 = await client.delete(f"/api/v1/patients/{patient_id}")
    assert response2.status_code == 404

    events = operational_store.audit_events()
    delete_events = [e for e in events if e.action == "DELETE_PATIENT"]
    assert len(delete_events) == 1
    assert delete_events[0].patient_id == patient_id
