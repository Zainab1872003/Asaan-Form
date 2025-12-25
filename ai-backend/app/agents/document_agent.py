from app.schemas.state import AgentState
from app.services.ocr_service import extract_text_from_image
from app.utils.llm import get_llm
import json

llm = get_llm()

def document_agent(state: AgentState) -> AgentState:
    files = state.get("files", [])

    if not files:
        return state

    raw_text = extract_text_from_image(files[0])

    prompt = f"""
You are a document understanding agent.

Convert the following OCR text into clean, structured JSON.
Use meaningful keys.
If a value is missing, use null.

OCR Text:
{raw_text}

Return ONLY valid JSON.
"""

    response = llm.invoke(prompt).content

    try:
        structured_json = json.loads(response)
    except Exception:
        structured_json = {"error": "Invalid JSON returned", "raw": response}

    return {
        **state,
        "raw_text": raw_text,
        "extracted_json": structured_json
    }
