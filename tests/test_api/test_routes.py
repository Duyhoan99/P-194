import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_chat_empty_message(client):
    response = await client.post("/api/v1/chat", json={"message": ""})
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_chat_returns_final_response_without_internal_analysis(client, monkeypatch):
    class FakeAgent:
        async def ainvoke(self, _state):
            return {"response": "Final answer", "analysis": "internal plan"}

    monkeypatch.setattr("src.api.routes.agent", FakeAgent())

    response = await client.post("/api/v1/chat", json={"message": "Question"})

    assert response.status_code == 200
    assert response.json() == {"response": "Final answer", "analysis": ""}


@pytest.mark.asyncio
async def test_agent_status(client):
    response = await client.get("/api/v1/status")
    assert response.status_code == 200
