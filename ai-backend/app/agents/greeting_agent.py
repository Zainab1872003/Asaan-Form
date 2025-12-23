# First LangGraph Node
from app.schemas.state import GraphState
from app.utils.llm import get_llm

llm = get_llm()

def greeting_agent(state: GraphState) -> GraphState:
    user_input = state["user_input"]

    prompt = f"""
    You are a friendly AI assistant for an Auto Form Filling System.
    Greet the user and briefly explain what you can do.

    User message: {user_input}
    """

    response = llm.invoke(prompt)

    return {
        "user_input": user_input,
        "response": response.content
    }
