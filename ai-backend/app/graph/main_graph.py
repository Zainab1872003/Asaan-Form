from langgraph.graph import StateGraph, END
from app.schemas.state import AgentState

from app.agents.intent_agent import intent_agent
from app.agents.document_agent import document_agent

def route(state: AgentState):
    if state.get("intent") == "document":
        return "document_agent"
    return END

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("intent_agent", intent_agent)
    graph.add_node("document_agent", document_agent)

    graph.set_entry_point("intent_agent")

    graph.add_conditional_edges(
        "intent_agent",
        route,
        {
            "document_agent": "document_agent",
            END: END
        }
    )

    graph.add_edge("document_agent", END)

    return graph.compile()

main_graph = build_graph()
