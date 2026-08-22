"""Rule-first task routing and non-clinical safety policy."""

from __future__ import annotations

import re
from typing import Literal

from src.agents.contracts import AgentRequest
from src.agents.retrieval.router import DomainNeed, QueryPlanner, RetrievalPlan

QuestionType = Literal["structured", "notes", "hybrid", "not_allowed", "not_allowed_interaction", "narrative", "temporal", "mixed"]

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
_INTERACTION_REQUESTS = (
    "tương tác",
    "interaction",
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
_PROMPT_OVERRIDE = re.compile(
    r"\b(ignore|disregard|forget|override)\b.{0,48}"
    r"\b(previous|prior|system|developer)\b.{0,32}"
    r"\b(instruction|prompt|message)s?\b",
    re.IGNORECASE,
)


def _normalize_patient_token(token: str) -> str:
    digits = "".join(character for character in token if character.isdigit())
    return f"PAT-{digits}"


def classify_request(request: AgentRequest) -> QuestionType | dict:
    """Classify without allowing model/user text to change the locked scope."""
    if request.task_type == "review_generation":
        # Review generation is a server-owned workflow, not a user chat turn.
        # Keep it deterministic so an unavailable planner can never turn a
        # clarification/greeting into a persisted SOAP summary.
        return RetrievalPlan(
            task_type="summary",
            needs=[DomainNeed(domain="all")],
            use_structured=True,
            use_semantic=False,
            use_lexical=False,
            retrieval_required=True,
            strict_intent="NONE",
        ).model_dump()

    question = (request.question or "").strip().casefold()
    mentioned_patients = {_normalize_patient_token(token) for token in _PATIENT_TOKEN.findall(question)}
    if mentioned_patients - {request.patient_id.upper()}:
        return "not_allowed"
    if _PROMPT_OVERRIDE.search(question):
        return "not_allowed"
    if any(term in question for term in _TREATMENT_REQUESTS):
        return "not_allowed"
    if any(term in question for term in _INTERACTION_REQUESTS):
        return "not_allowed_interaction"

    # Use QueryPlanner to get the validated RetrievalPlan
    planner = QueryPlanner()
    plan = planner.plan(request.question or "")

    # If the plan is out of scope, return not_allowed
    if plan.task_type == "out_of_scope":
        return "not_allowed"

    return plan.model_dump()
