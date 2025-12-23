# LLM Loader
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

def get_llm():
    return ChatOpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("OPENROUTER_BASE_URL"),
        model="openai/gpt-oss-120b:free",
        temperature=0.3,
        default_headers={
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Asaan Form FYP"
        }
    )