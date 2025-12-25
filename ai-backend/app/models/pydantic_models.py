from pydantic import BaseModel
from typing import List

class ChatRequest(BaseModel):
    user_id: str
    message: str
    files: List[str] = []  # paths to uploaded files

class ChatResponse(BaseModel):
    response: str
    extracted_data: dict | None = None
    intent: str