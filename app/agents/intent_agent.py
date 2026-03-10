from schemas.state import AgentState
from utils.llm import get_llm, generate_response_from_prompt

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

    llm = get_llm()
    content = generate_response_from_prompt(llm, prompt)
    intent = (content or "").strip().lower()

    # safety fallback
    if intent not in {"chat", "document", "form"}:
        intent = "chat"

    return {
        "intent": intent
    }