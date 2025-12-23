# LangGraph Workflow
from langgraph.graph import StateGraph, END
from app.schemas.state import GraphState
from app.agents.greeting_agent import greeting_agent

def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("greeting", greeting_agent)
    graph.set_entry_point("greeting")
    graph.add_edge("greeting", END)

    return graph.compile()
