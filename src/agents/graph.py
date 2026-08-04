from langgraph.graph import END, StateGraph

from src.agents.nodes.example_node import analyze_node, respond_node
from src.agents.state import AgentState


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
