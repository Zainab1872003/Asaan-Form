"""
Document Upload API Routes - GridFS Compatible

Architecture:
- AI backend receives file bytes, processes (OCR + LLM extraction), returns JSON
- AI backend NEVER saves files permanently
- Node.js receives the JSON result and saves to MongoDB
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Optional

from app.services.document_processing_service import document_processing_service

router = APIRouter(prefix="/document", tags=["Documents"])


@router.post("/upload/{user_id}")
async def upload_document(
    user_id: str,
    file: UploadFile = File(...),
    document_type: Optional[str] = Query(None, description="Type of document: id_card, certificate, passport, etc."),
    languages: str = Query("english,urdu", description="Comma-separated languages for OCR"),
):
    """
    Process a document (ID card, certificate, etc.) and return extracted data as JSON.

    AI backend:
    1. Writes file to a TEMP location (needed by Docling/OCR tools)
    2. Runs OCR (English + Urdu)
    3. Extracts structured data with LLM
    4. DELETES the temp file
    5. Returns the extracted JSON

    Node.js backend:
    - Receives the JSON
    - Saves the original file to GridFS
    - Saves the extracted data to MongoDB Document record
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    allowed_exts = {"png", "jpg", "jpeg", "pdf"}
    if file_ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '.{file_ext}'. Allowed: {allowed_exts}"
        )

    lang_list = [lang.strip().lower() for lang in languages.split(",")]

    try:
        result = await document_processing_service.process_document(
            user_id,
            file,
            document_type,
            lang_list,
        )
        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")