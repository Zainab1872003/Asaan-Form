from app.schemas.state import AgentState
from app.utils.llm import get_llm
import logging

logger = logging.getLogger(__name__)

def intent_agent(state: AgentState) -> AgentState:
    user_input = state.get("user_input", "")

    prompt = (
        "You are an intent classification agent.\n\n"
        "Classify the user's intent into ONLY one of the following values:\n"
        "- chat\n"
        "- document\n"
        "- form\n\n"
        "User input:\n"
        f"{user_input}\n\n"
        "Return ONLY the intent value."
    )

    try:
        llm = get_llm()
        response = llm.invoke(prompt)
        intent = response.content.strip().lower()

        # safety fallback
        if intent not in {"chat", "document", "form"}:
            intent = "chat"
    except ValueError as e:
        # API key not configured
        logger.error(f"LLM configuration error: {e}")
        # Default to document intent if LLM is not available
        intent = "document"
    except Exception as e:
        # Other LLM errors (authentication, network, etc.)
        logger.error(f"LLM invocation error: {e}")
        # Default to document intent on error
        intent = "document"

    return {
        "intent": intent
    }
