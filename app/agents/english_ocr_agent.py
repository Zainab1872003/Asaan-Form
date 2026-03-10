from schemas.state import AgentState
from services.ocr_service import extract_english_text

def english_ocr_agent(state: AgentState) -> AgentState:
    files = state.get("files", [])
    if not files:
        return state

    text = extract_english_text(files[0])

    return {
        **state,
        "english_text": text
    }