# LLM Loader
from langchain_openai import ChatOpenAI
from app.config import settings

def get_llm():
    """Get LLM instance using settings from config."""
    if not settings.OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY is not set in .env file. "
            "Please set it in your .env file or environment variables."
        )
    
    return ChatOpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        default_headers={
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Asaan Form FYP"
        }
    )