# First LangGraph Node
from app.schemas.state import GraphState
from app.utils.llm import get_llm
import logging

logger = logging.getLogger(__name__)

def greeting_agent(state: GraphState) -> GraphState:
    user_input = state["user_input"]

    prompt = f"""
    You are a friendly AI assistant for an Auto Form Filling System.
    Greet the user and briefly explain what you can do.

    User message: {user_input}
    """

    try:
        llm = get_llm()
        response = llm.invoke(prompt)
        response_content = response.content
    except ValueError as e:
        # API key not configured
        logger.error(f"LLM configuration error: {e}")
        response_content = "I'm sorry, but the AI service is not properly configured. Please contact the administrator."
    except Exception as e:
        # Other LLM errors (authentication, network, etc.)
        logger.error(f"LLM invocation error: {e}")
        response_content = "I'm sorry, but I'm experiencing technical difficulties. Please try again later."

    return {
        "user_input": user_input,
        "response": response_content
    }
