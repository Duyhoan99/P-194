from __future__ import annotations

from typing import Annotated, Literal, TypedDict
from langgraph.graph.message import add_messages

from src.agents.contracts import AgentError, AgentRequest, AgentResult, VerifiedClaim
from src.agents.evidence import ScopedEvidence
from src.agents.generation import ProposedClaim
from src.agents.policy import QuestionType
from src.agents.verification import ClaimVerification


class AgentState(TypedDict, total=False):
    """State schema cho LangGraph agent.

    Mỗi node đọc và ghi vào state này.
    total=False cho phép tất cả fields là optional.
    """

    query: str
    context: str
    analysis: str
    response: str
    error: str
    metadata: dict


class RuntimeScope(TypedDict):
    tenant_id: str
    patient_id: str
    request_id: str


class ClinicalReviewState(TypedDict, total=False):
    """Internal state from ARCHITECTURE.md 11.2; never returned directly."""
    messages: Annotated[list, add_messages]
    active_focus_entities: list[str]
    request: AgentRequest
    runtime_scope: RuntimeScope
    question_type: QuestionType
    evidence_packet: list[ScopedEvidence]
    retrieved_evidence: list[ScopedEvidence]
    proposed_claims: list[ProposedClaim]
    claims: list[VerifiedClaim]
    unsupported_claims: list[VerifiedClaim]
    conflicts: list[dict]
    verification_results: list[ClaimVerification]
    status: Literal[
        "running",
        "answered",
        "not_found",
        "conflicting",
        "not_allowed",
        "error",
    ]
    errors: list[AgentError]
    public_response: AgentResult
