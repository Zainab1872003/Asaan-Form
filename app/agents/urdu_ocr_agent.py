from schemas.state import AgentState
from services.urdu_ocr_service import extract_urdu_text

def urdu_ocr_agent(state: AgentState) -> AgentState:
    files = state.get("files", [])
    if not files:
        # Return an empty dict if no changes are made
        return {} 

    text = extract_urdu_text(files[0])

    # ONLY return the key you want to change
    return {
        "urdu_text": text
    }