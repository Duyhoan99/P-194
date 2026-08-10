"""Rule-first task routing and non-clinical safety policy."""

from __future__ import annotations

import re
from typing import Literal

from src.agents.contracts import AgentRequest

QuestionType = Literal["structured", "notes", "hybrid", "not_allowed"]

_TREATMENT_REQUESTS = (
    "đổi thuốc",
    "ngừng thuốc",
    "nên dùng",
    "nên ngừng",
    "nên đổi",
    "kê đơn",
    "khuyến nghị điều trị",
    "recommend treatment",
    "which medication should",
)
_NOTE_TERMS = (
    "ghi chú",
    "đau ngực",
    "khó thở",
    "hạ đường huyết",
    "triệu chứng",
    "tự khai",
    "note",
    "symptom",
)
_STRUCTURED_TERMS = (
    "hba1c",
    "egfr",
    "glucose",
    "xét nghiệm",
    "liều",
    "thuốc",
    "metformin",
    "dị ứng",
    "trend",
    "bao nhiêu",
)
_PATIENT_TOKEN = re.compile(r"PAT-?\d{3}", re.IGNORECASE)


def _normalize_patient_token(token: str) -> str:
    digits = "".join(character for character in token if character.isdigit())
    return f"PAT-{digits}"


def classify_request(request: AgentRequest) -> QuestionType:
    """Classify without allowing model/user text to change the locked scope."""
    if request.task_type == "review_generation":
        return "hybrid"
    question = (request.question or "").strip().casefold()
    mentioned_patients = {_normalize_patient_token(token) for token in _PATIENT_TOKEN.findall(question)}
    if mentioned_patients - {request.patient_id.upper()}:
        return "not_allowed"
    if any(term in question for term in _TREATMENT_REQUESTS):
        return "not_allowed"
    has_notes = any(term in question for term in _NOTE_TERMS)
    has_structured = any(term in question for term in _STRUCTURED_TERMS)
    if has_notes and has_structured:
        return "hybrid"
    if has_notes:
        return "notes"
    if has_structured:
        return "structured"
    return "hybrid"
