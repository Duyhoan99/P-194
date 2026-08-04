import json

from src.agents.tools import example_tool


def _search(query: str) -> dict:
    return json.loads(example_tool.search_knowledge.invoke({"query": query}))


def test_search_knowledge_returns_ranked_local_results(monkeypatch, tmp_path):
    (tmp_path / "clinical.md").write_text(
        "Laboratory evidence\n\nCreatinine results require value, unit, and timestamp.",
        encoding="utf-8",
    )
    (tmp_path / "unrelated.md").write_text("Administrative scheduling information.", encoding="utf-8")
    monkeypatch.setattr(example_tool, "KNOWLEDGE_BASE_DIR", tmp_path)
    example_tool._load_knowledge_base.cache_clear()

    result = _search("creatinine unit timestamp")

    assert result["status"] == "SUCCESS"
    assert result["results"][0]["source"] == "clinical.md"
    assert "Creatinine" in result["results"][0]["text"]


def test_search_knowledge_reports_not_loaded_without_documents(monkeypatch, tmp_path):
    monkeypatch.setattr(example_tool, "KNOWLEDGE_BASE_DIR", tmp_path)
    example_tool._load_knowledge_base.cache_clear()

    result = _search("clinical evidence")

    assert result == {"status": "NOT_LOADED", "results": []}


def test_search_knowledge_rejects_blank_query():
    result = _search("   ")

    assert result == {"status": "INVALID_QUERY", "results": []}
