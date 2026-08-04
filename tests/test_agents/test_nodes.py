from types import SimpleNamespace

import pytest

from src.agents.nodes import example_node


class FakeChatModel:
    def __init__(self, content: str = "model output", error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.calls: list[object] = []

    async def ainvoke(self, messages: object) -> SimpleNamespace:
        self.calls.append(messages)
        if self.error:
            raise self.error
        return SimpleNamespace(content=self.content)


@pytest.mark.asyncio
async def test_analyze_node_calls_configured_chat_model(monkeypatch):
    model = FakeChatModel("The user asks for an evidence-grounded summary.")
    monkeypatch.setattr(example_node, "get_llm", lambda: model)

    result = await example_node.analyze_node({"query": "Summarize the evidence."})

    assert result["analysis"] == "The user asks for an evidence-grounded summary."
    assert len(model.calls) == 1


@pytest.mark.asyncio
async def test_respond_node_calls_model_and_returns_only_final_response(monkeypatch):
    model = FakeChatModel("Only the requested answer.")
    monkeypatch.setattr(example_node, "get_llm", lambda: model)

    result = await example_node.respond_node(
        {"query": "What is relevant?", "analysis": "Identify relevant evidence."}
    )

    assert result == {"response": "Only the requested answer."}
    assert len(model.calls) == 1


@pytest.mark.asyncio
async def test_nodes_fail_safely_when_model_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        example_node,
        "get_llm",
        lambda: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )

    analysis = await example_node.analyze_node({"query": "Question"})
    response = await example_node.respond_node({"query": "Question", **analysis})

    assert analysis["error"] == "AI analysis is currently unavailable."
    assert response["response"] == "The AI Agent is temporarily unavailable. Please try again."
