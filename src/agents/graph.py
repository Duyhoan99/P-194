from typing import Any

from langgraph.graph import END, START, StateGraph

from src.agents.contracts import AgentError, AgentRequest, AgentResult
from src.agents.nodes.clinical_nodes import (
    abstain_node,
    classify_question_node,
    finalize_response_node,
    generate_grounded_node,
    retrieve_evidence_node,
    validate_scope_node,
    verify_claims_node,
)
from src.agents.nodes.example_node import analyze_node, respond_node
from src.agents.state import AgentState, ClinicalReviewState, RuntimeScope


def should_continue(state: AgentState) -> str:
    """Always reach the response node so model failures get a safe message."""
    return "respond"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("analyze", analyze_node)
    graph.add_node("respond", respond_node)

    # Add edges
    graph.set_entry_point("analyze")
    graph.add_conditional_edges("analyze", should_continue)
    graph.add_edge("respond", END)

    return graph.compile()


agent = build_graph()


def _route_after_scope(state: ClinicalReviewState) -> str:
    return "finalize" if state.get("status") == "error" else "classify"


def _route_after_classification(state: ClinicalReviewState) -> str:
    return "abstain" if state.get("question_type") == "not_allowed" else "retrieve"


def _route_after_retrieval(state: ClinicalReviewState) -> str:
    return "generate" if state.get("retrieved_evidence") else "abstain"


def _route_after_verification(state: ClinicalReviewState) -> str:
    return "abstain" if state.get("status") == "not_found" else "finalize"


def build_clinical_graph():
    """Build the fixture/backend-adapter graph specified in ARCHITECTURE.md 11.3."""
    graph = StateGraph(ClinicalReviewState)
    graph.add_node("validate_scope", validate_scope_node)
    graph.add_node("classify", classify_question_node)
    graph.add_node("retrieve", retrieve_evidence_node)
    graph.add_node("generate", generate_grounded_node)
    graph.add_node("verify", verify_claims_node)
    graph.add_node("abstain", abstain_node)
    graph.add_node("finalize", finalize_response_node)
    graph.add_edge(START, "validate_scope")
    graph.add_conditional_edges(
        "validate_scope",
        _route_after_scope,
        {"classify": "classify", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "classify",
        _route_after_classification,
        {"retrieve": "retrieve", "abstain": "abstain"},
    )
    graph.add_conditional_edges(
        "retrieve",
        _route_after_retrieval,
        {"generate": "generate", "abstain": "abstain"},
    )
    graph.add_edge("generate", "verify")
    graph.add_conditional_edges(
        "verify",
        _route_after_verification,
        {"finalize": "finalize", "abstain": "abstain"},
    )
    graph.add_edge("abstain", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


clinical_agent = build_clinical_graph()


def run_agent(
    request: AgentRequest | dict[str, Any],
    *,
    runtime_scope: RuntimeScope | None = None,
) -> AgentResult:
    """Run WP2 with a locked scope and return only the contract public result."""
    validated = request if isinstance(request, AgentRequest) else AgentRequest.model_validate(request)
    locked_scope: RuntimeScope = runtime_scope or {
        "tenant_id": validated.tenant_id,
        "patient_id": validated.patient_id,
        "request_id": validated.request_id,
    }
    try:
        state = clinical_agent.invoke(
            {
                "request": validated,
                "runtime_scope": locked_scope,
                "status": "running",
                "errors": [],
            },
            config={"recursion_limit": 16},
        )
        result = state.get("public_response")
        if isinstance(result, AgentResult):
            return result
    except Exception:
        pass
    return AgentResult(
        task_type=validated.task_type,
        status="error",
        data_watermark=validated.data_watermark,
        sections=[] if validated.task_type == "review_generation" else None,
        claims=[],
        citations=[],
        errors=[AgentError(code="AGENT_EXECUTION_ERROR", message="Agent execution failed safely.")],
    )
