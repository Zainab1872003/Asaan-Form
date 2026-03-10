from langgraph.graph import StateGraph, END
from schemas.state import AgentState

from agents.intent_agent import intent_agent
from agents.english_ocr_agent import english_ocr_agent
from agents.urdu_ocr_agent import urdu_ocr_agent
from agents.bilingual_merge_agent import bilingual_merge_agent
from agents.form_agent import form_agent


# --------------------------------------------------
# Intent Router
# --------------------------------------------------
def route(state: AgentState):
    intent = state.get("intent")
    if intent == "document":
        return ["english_ocr", "urdu_ocr"]  # FAN-OUT
    elif intent == "form":
        return "form_agent"
    return END


def build_graph():
    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("intent_agent", intent_agent)
    graph.add_node("english_ocr", english_ocr_agent)
    graph.add_node("urdu_ocr", urdu_ocr_agent)
    graph.add_node("merge", bilingual_merge_agent)
    graph.add_node("form_agent", form_agent)

    # Entry
    graph.set_entry_point("intent_agent")

    # FAN-OUT routing
    graph.add_conditional_edges(
        "intent_agent",
        route,
        {
            "english_ocr": "english_ocr",
            "urdu_ocr": "urdu_ocr",
            "form_agent": "form_agent",
            END: END
        }
    )

    # FAN-IN (join)
    graph.add_edge("english_ocr", "merge")
    graph.add_edge("urdu_ocr", "merge")

    graph.add_edge("merge", END)
    graph.add_edge("form_agent", END)

    return graph.compile()


main_graph = build_graph()