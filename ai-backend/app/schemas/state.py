# Shared Graph State
from typing import TypedDict, Optional

class GraphState(TypedDict):
    user_input: str
    response: Optional[str]
