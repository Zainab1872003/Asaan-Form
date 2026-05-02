"""
Form Upload API Routes - GridFS Compatible

Architecture:
- AI backend receives form PDF bytes, processes (Docling + LLM field extraction), returns JSON
- AI backend SAVES the form locally (needed for fill-existing lookups by form_id)
- Node.js receives form_id and form_fields JSON, saves to MongoDB Form record
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional

from app.services.form_processing_service import form_processing_service

router = APIRouter(prefix="/form", tags=["Forms"])


@router.post("/upload/{user_id}")
async def upload_form(
    user_id: str,
    file: UploadFile = File(...),
    form_name: Optional[str] = Query(None, description="Optional name for the form"),
):
    """
    Upload and process a form template.

    AI backend:
    1. Saves form locally (needed later for PDF overlay — original PDF referenced by form_id)
    2. Converts PDF to images (Docling needs image files)
    3. Runs Docling on each page
    4. Extracts form fields with coordinates via LLM
    5. Returns form_id + form_fields JSON

    Node.js backend:
    - Stores formIdAI (= form_id from this response) in MongoDB Form record
    - Stores formSchema (= form_fields) in MongoDB Form record
    - Stores original file in GridFS (for serving to users)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    try:
        result = await form_processing_service.process_form(
            user_id=user_id,
            file=file,
            form_name=form_name,
        )

        form_data = result.get("data", {})

        return JSONResponse(content={
            "success": result.get("success", False),
            "user_id": user_id,
            "data": {
                "form_id": form_data.get("form_id"),
                "form_fields": form_data.get("form_fields"),
            },
            "form_result": result,
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Form processing failed: {str(e)}")


# Keep minimal stubs for compatibility
@router.get("/list/{user_id}")
async def list_user_forms(user_id: str):
    return JSONResponse(content={"message": "List functionality is in Node.js backend"})


@router.get("/fields/{user_id}/{form_id}")
async def get_form_fields(user_id: str, form_id: str):
    return JSONResponse(content={"message": "Form fields retrieval is in Node.js backend"})