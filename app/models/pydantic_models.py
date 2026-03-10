"""
Re-export all pydantic models
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any


# Legacy models (keep for backward compatibility)
class ChatRequest(BaseModel):
    user_id: str
    message: str
    files: List[str] = []  # paths to uploaded files


class ChatResponse(BaseModel):
    response: str
    extracted_data: Optional[Dict[str, Any]] = None
    intent: str