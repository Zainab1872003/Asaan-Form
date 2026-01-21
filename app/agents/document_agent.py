from app.schemas.state import AgentState
from app.services.ocr_service import extract_text_from_image
from app.utils.llm import get_llm
import json
import logging

logger = logging.getLogger(__name__)

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

    try:
        llm = get_llm()
        response = llm.invoke(prompt).content
    except ValueError as e:
        # API key not configured
        logger.error(f"LLM configuration error: {e}")
        return {
            **state,
            "raw_text": raw_text,
            "extracted_json": {
                "error": "LLM not configured. Please set OPENROUTER_API_KEY in .env file.",
                "raw_text": raw_text
            }
        }
    except Exception as e:
        # Other LLM errors (authentication, network, etc.)
        logger.error(f"LLM invocation error: {e}")
        return {
            **state,
            "raw_text": raw_text,
            "extracted_json": {
                "error": f"LLM error: {str(e)}",
                "raw_text": raw_text
            }
        }

    try:
        structured_json = json.loads(response)
    except Exception:
        structured_json = {"error": "Invalid JSON returned", "raw": response}

    return {
        **state,
        "raw_text": raw_text,
        "extracted_json": structured_json
    }
