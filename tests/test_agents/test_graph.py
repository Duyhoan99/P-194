import pytest

from src.agents.graph import agent
from src.agents.nodes import example_node


class FakeChatModel:
    async def ainvoke(self, _messages):
        class Message:
            content = "Mocked model response."

        return Message()


@pytest.mark.asyncio
async def test_agent_basic_flow(monkeypatch):
    monkeypatch.setattr(example_node, "get_llm", lambda: FakeChatModel())
    result = await agent.ainvoke({"query": "Hello"})
    assert result["response"] == "Mocked model response."


@pytest.mark.asyncio
async def test_agent_state_structure(monkeypatch):
    monkeypatch.setattr(example_node, "get_llm", lambda: FakeChatModel())
    result = await agent.ainvoke({"query": "Test query"})
    assert isinstance(result, dict)
    assert "query" in result
