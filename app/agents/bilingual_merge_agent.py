import json
from app.schemas.state import AgentState
from app.utils.llm import get_llm
import logging

logger = logging.getLogger(__name__)

def bilingual_merge_agent(state: AgentState) -> AgentState:
    english = state.get("english_text", "")
    urdu = state.get("urdu_text", "")

    prompt = f"""
You are a bilingual document understanding agent.

You are given OCR outputs from the SAME document.

Rules:
- Keys must be in English
- Merge information from BOTH OCRs
- Translate Urdu values to English
- Prefer clearer values
- Use null if missing

English OCR:
{english}

Urdu OCR:
{urdu}

Return ONLY valid JSON.
"""

    try:
        llm = get_llm()
        response = llm.invoke(prompt).content
    except ValueError as e:
        # API key not configured
        logger.error(f"LLM configuration error: {e}")
        merged = {
            "error": "LLM not configured. Please set OPENROUTER_API_KEY in .env file.",
            "english_text": english,
            "urdu_text": urdu
        }
    except Exception as e:
        # Other LLM errors (authentication, network, etc.)
        logger.error(f"LLM invocation error: {e}")
        merged = {
            "error": f"LLM error: {str(e)}",
            "english_text": english,
            "urdu_text": urdu
        }
    else:
        try:
            merged = json.loads(response)
        except Exception:
            merged = {"error": "Invalid JSON", "raw": response}

    return {
        **state,
        "merged_json": merged
    }
