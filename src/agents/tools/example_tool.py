import ast
import json
import operator
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from langchain_core.tools import tool

# The demo intentionally uses a local, approved corpus only. It never performs
# an unbounded web search or sends knowledge-base contents to another service.
KNOWLEDGE_BASE_DIR = Path(os.getenv("KNOWLEDGE_BASE_DIR", "./data/knowledge"))
_SUPPORTED_SUFFIXES = {".md", ".txt", ".json"}
_TOKEN_PATTERN = re.compile(r"[\w-]+", re.UNICODE)


@dataclass(frozen=True)
class KnowledgeChunk:
    source: str
    text: str
    tokens: frozenset[str]


def _tokens(value: str) -> frozenset[str]:
    return frozenset(token.casefold() for token in _TOKEN_PATTERN.findall(value))


@lru_cache(maxsize=1)
def _load_knowledge_base() -> tuple[KnowledgeChunk, ...]:
    """Load bounded local text chunks for deterministic lexical retrieval."""
    base_dir = Path(KNOWLEDGE_BASE_DIR)
    if not base_dir.is_dir():
        return ()

    chunks: list[KnowledgeChunk] = []
    for path in sorted(base_dir.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in _SUPPORTED_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for raw_chunk in re.split(r"\n\s*\n", content):
            text = " ".join(raw_chunk.split())
            if text:
                chunks.append(
                    KnowledgeChunk(
                        source=path.relative_to(base_dir).as_posix(),
                        text=text[:2000],
                        tokens=_tokens(text),
                    )
                )
    return tuple(chunks)


@tool
def search_knowledge(query: str) -> str:
    """Search the local approved knowledge corpus with deterministic lexical ranking.

    Returns JSON with ``SUCCESS``, ``NO_MATCH``, ``NOT_LOADED`` or
    ``INVALID_QUERY`` status. The tool never invents content when no corpus is
    present and never falls back to an external search provider.
    """
    normalized_query = query.strip()
    if not normalized_query:
        return json.dumps({"status": "INVALID_QUERY", "results": []})

    chunks = _load_knowledge_base()
    if not chunks:
        return json.dumps({"status": "NOT_LOADED", "results": []})

    query_tokens = _tokens(normalized_query)
    ranked: list[tuple[int, KnowledgeChunk]] = []
    for chunk in chunks:
        overlap = len(query_tokens & chunk.tokens)
        if overlap:
            phrase_bonus = 1 if normalized_query.casefold() in chunk.text.casefold() else 0
            ranked.append((overlap * 10 + phrase_bonus, chunk))

    ranked.sort(key=lambda item: (-item[0], item[1].source, item[1].text))
    results = [
        {"source": chunk.source, "text": chunk.text, "score": score}
        for score, chunk in ranked[:5]
    ]
    status = "SUCCESS" if results else "NO_MATCH"
    return json.dumps({"status": status, "results": results}, ensure_ascii=False)


# Safe operator mapping for calculator.
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


@tool
def calculate(expression: str) -> str:
    """Calculate a mathematical expression safely without using eval."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_node(tree.body)
        return str(result)
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError) as error:
        return f"Calculation error: {error}"


def _eval_node(node: ast.AST) -> float:
    """Recursively evaluate AST node using safe operators only."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value)}")
    if isinstance(node, ast.UnaryOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op_func(_eval_node(node.operand))
    if isinstance(node, ast.BinOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op_func(_eval_node(node.left), _eval_node(node.right))
    raise ValueError(f"Unsupported expression: {type(node).__name__}")
