"""
Form Agent for LangGraph
Processes forms to extract fields with coordinates and types.
"""

from pathlib import Path
from typing import Dict
from fastapi import UploadFile
from schemas.state import AgentState
from services.form_processing_service import FormProcessingService

# Initialize service
_form_service = FormProcessingService()


def form_agent(state: AgentState) -> AgentState:
    """
    Process a form file to extract fields with coordinates and types.
    
    Uses the form processing service to:
    1. Convert PDF to 300 DPI images (if needed)
    2. Process with Docling to get structure
    3. Extract form fields with LLM
    """
    files = state.get("files", [])
    user_id = state.get("user_id", "default")
    
    if not files:
        return {
            **state,
            "form_result": {
                "success": False,
                "error": "No file provided"
            }
        }
    
    file_path = Path(files[0])
    
    if not file_path.exists():
        return {
            **state,
            "form_result": {
                "success": False,
                "error": f"File not found: {file_path}"
            }
        }
    
    try:
        # Create an UploadFile from the file path
        # This allows us to use the existing form processing service
        file_obj = open(file_path, 'rb')
        upload_file = UploadFile(
            filename=file_path.name,
            file=file_obj
        )
        
        # Process the form using the service
        import asyncio
        
        # Run the async process_form method
        result = asyncio.run(_form_service.process_form(
            user_id=user_id,
            file=upload_file,
            form_name=None
        ))
        
        file_obj.close()
        
        return {
            **state,
            "form_result": result
        }
        
    except Exception as e:
        return {
            **state,
            "form_result": {
                "success": False,
                "error": str(e),
                "errors": [str(e)]
            }
        }