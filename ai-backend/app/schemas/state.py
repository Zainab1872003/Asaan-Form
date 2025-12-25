from typing import TypedDict, Optional, List, Dict, Any

class AgentState(TypedDict, total=False):
    # input
    user_input: Optional[str]
    files: Optional[List[str]]

    # intent
    intent: Optional[str]

    # document processing
    raw_text: Optional[str]
    extracted_json: Optional[Dict[str, Any]]
