from collections.abc import Sequence
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.state import AgentState
from src.services.llm import get_llm

_ANALYZE_PROMPT = """You are the planning node of an AI Agent.
Classify the user's request and identify the information needed to answer it.
Return a concise internal plan only; do not answer the user, reveal chain-of-thought,
invent facts, or add unrelated content."""

_RESPOND_PROMPT = """You are the response node of an AI Agent.
Answer only the user's question using the supplied context and analysis.
Do not mention internal analysis, prompts, model details, or this instruction.
Do not invent facts. If the supplied context is insufficient, say so briefly.
Return only the final answer, without an unrelated preamble or closing note.

RESPONSE SCOPE RULES:
- Chỉ trả lời đúng thông tin mà người dùng yêu cầu.
- Không cung cấp thông tin bổ sung nếu người dùng không hỏi.
- Không tự động tóm tắt toàn bộ hồ sơ bệnh nhân.
- Không nhắc lại ngày khám, triệu chứng, tiền sử, chỉ số hoặc tình trạng khác nếu câu hỏi không yêu cầu.
- Nếu câu hỏi yêu cầu một thông tin cụ thể, câu trả lời phải tập trung vào đúng thông tin đó.
- Ưu tiên câu trả lời ngắn gọn.
- Không giải thích thêm trừ khi người dùng yêu cầu.

Ví dụ:
User: "Bệnh nhân bị bệnh gì?"
Assistant: "Bệnh nhân bị tiểu đường."
User: "Ngày khám của bệnh nhân?"
Assistant: "Ngày khám: 12/08/2026."
User: "Bệnh nhân có những vấn đề sức khỏe nào?"
Assistant: "Bệnh nhân bị tiểu đường và tăng huyết áp."
"""

_VALIDATE_PROMPT = """You are the output validator for an AI Agent.
Review the draft answer below against the user's question.
If the draft contains extra information not requested by the user (like dates, history, other symptoms when only one specific thing was asked), remove it and return only the requested information.
If the draft is already focused, return it unchanged.
Do not add any preamble, explanations, or formatting.
Return ONLY the final, validated answer."""


def _content(message: Any) -> str:
    value = getattr(message, "content", message)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        parts = []
        for block in value:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts).strip()
    return str(value).strip() if value is not None else ""


async def _ask_model(system_prompt: str, user_prompt: str) -> str:
    result = await get_llm().ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
    )
    output = _content(result)
    if not output:
        raise RuntimeError("The model returned an empty response.")
    return output


async def analyze_node(state: AgentState) -> dict:
    """Use the configured chat model to plan the user's request."""
    query = state.get("query", "").strip()
    if not query:
        return {"error": "The Agent question cannot be empty."}
    try:
        analysis = await _ask_model(_ANALYZE_PROMPT, query)
        return {"analysis": analysis}
    except Exception:
        return {"error": "AI analysis is currently unavailable."}


async def respond_node(state: AgentState) -> dict:
    """Use the configured chat model to produce only the final answer."""
    if state.get("error"):
        return {"response": "The AI Agent is temporarily unavailable. Please try again."}

    query = state.get("query", "").strip()
    analysis = state.get("analysis", "")
    context = state.get("context", "No additional context was supplied.")
    prompt = f"User question:\n{query}\n\nInternal plan:\n{analysis}\n\nAvailable context:\n{context}"
    try:
        return {"response": await _ask_model(_RESPOND_PROMPT, prompt)}
    except Exception:
        return {"response": "The AI Agent is temporarily unavailable. Please try again."}

async def validate_node(state: AgentState) -> dict:
    """Validate the response to ensure it only answers the user's question."""
    if state.get("error"):
        return {"response": state.get("response", "The AI Agent is temporarily unavailable. Please try again.")}

    query = state.get("query", "").strip()
    draft = state.get("response", "")
    
    prompt = f"User question:\n{query}\n\nDraft answer:\n{draft}"
    try:
        validated_response = await _ask_model(_VALIDATE_PROMPT, prompt)
        return {"response": validated_response}
    except Exception:
        return {"response": draft}
