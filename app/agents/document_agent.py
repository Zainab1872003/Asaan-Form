import json
from schemas.state import AgentState
from services.ocr_service import extract_text_from_image
from utils.llm import get_llm, generate_response_from_prompt

def document_agent(state: AgentState) -> AgentState:
    files = state.get("files", [])

    if not files:
        return state

    raw_text = extract_text_from_image(files[0])
    if(raw_text):
        print(raw_text)
    else:
        print("empty")

    # Guard against empty OCR
    if not raw_text.strip():
        return {
            **state,
            "raw_text": "",
            "extracted_json": {"error": "No readable text found in document"},
        }

    prompt = f"""
You are a document understanding agent.

Convert the following OCR text into clean, structured JSON.
Use meaningful keys.
If a value is missing or unreadable, use null.

OCR Text:
{raw_text}

Return ONLY valid JSON.
"""
    llm = get_llm()
    response = generate_response_from_prompt(llm, prompt)

    try:
        structured_json = json.loads(response or "{}")
    except Exception:
        structured_json = {"error": "Invalid JSON returned", "raw": response}

    return {
        **state,
        "raw_text": raw_text,
        "extracted_json": structured_json
    }