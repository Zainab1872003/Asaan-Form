# LLM: Groq only
from groq import Groq
from config import settings


def get_llm():
    """Get Groq client instance using settings from config."""
    if not settings.GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is not set in .env file. "
            "Please set it in your .env file or environment variables."
        )
    return Groq(
        api_key=settings.GROQ_API_KEY,
        max_retries=5,
        timeout=600.0,
    )


def generate_response(llm_client, messages, stream=False):
    """
    Generate chat completion from Groq.
    messages: list of dicts with "role" and "content", e.g.
      [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    """
    completion = llm_client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        top_p=1,
        stream=stream,
        stop=None,
    )
    if stream:
        return completion
    return completion.choices[0].message.content or ""


def generate_response_from_prompt(llm_client, user_prompt: str, system_prompt: str | None = None):
    """Convenience: generate from a single user prompt (optional system prompt). Returns content string."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    return generate_response(llm_client, messages)
