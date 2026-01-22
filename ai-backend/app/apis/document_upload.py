"""
Document Upload API Routes
Handles document (ID cards, certificates, etc.) upload and processing.

Documents provide DATA to fill forms.
This is SEPARATE from form processing.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from pathlib import Path
import json

from app.config import settings
from app.services.document_processing_service import document_processing_service

router = APIRouter(prefix="/document", tags=["Documents"])


# ============================================================================
# DOCUMENT UPLOAD AND PROCESSING
# ============================================================================

@router.post("/upload/{user_id}")
async def upload_document(
    user_id: str, 
    file: UploadFile = File(...),
    document_type: Optional[str] = Query(
        None, 
        description="Type of document: id_card, certificate, passport, etc."
    ),
    process: bool = Query(
        True, 
        description="Whether to process the document immediately"
    ),
    languages: str = Query(
        "english,urdu",
        description="Comma-separated languages for OCR: english, urdu"
    )
):
    """
    Upload and process a document (ID card, certificate, etc.)
    
    - Saves document in user's documents folder
    - If PDF: converts to 300 DPI images first
    - Runs OCR to extract text (English + Urdu) from all pages
    - Uses LLM to extract structured data
    
    Args:
        user_id: User identifier
        file: Document file (image or PDF)
        document_type: Optional type hint (id_card, certificate, passport)
        process: Whether to run OCR and extraction (default: True)
        languages: Languages for OCR (default: "english,urdu")
        
    Returns:
        Processing result with extracted data
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_ext = Path(file.filename).suffix.lower()
    allowed = [".png", ".jpg", ".jpeg", ".pdf"]
    if file_ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file_ext}'. Allowed: {allowed}"
        )
    
    # Parse languages
    lang_list = [l.strip().lower() for l in languages.split(",")]
    
    try:
        if process:
            # Run complete processing pipeline
            result = await document_processing_service.process_document(
                user_id, 
                file, 
                document_type,
                lang_list
            )
            return JSONResponse(content=result)
        else:
            # Just save without processing
            file_path, metadata = await document_processing_service.save_document(
                user_id, file, document_type
            )
            
            return JSONResponse(content={
                "message": "Document saved successfully",
                "user_id": user_id,
                "processed": False,
                "data": metadata
            })
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload/{user_id}/batch")
async def upload_multiple_documents(
    user_id: str, 
    files: List[UploadFile] = File(...),
    document_type: Optional[str] = Query(None),
    process: bool = Query(True),
    languages: str = Query("english,urdu")
):
    """
    Upload and process multiple documents at once
    
    Args:
        user_id: User identifier
        files: List of document files
        document_type: Optional type hint (applies to all)
        process: Whether to process documents
        languages: Languages for OCR
        
    Returns:
        Combined results with merged extracted data
    """
    if not process:
        # Just save all files without processing
        results = []
        for file in files:
            try:
                file_path, metadata = await document_processing_service.save_document(
                    user_id, file, document_type
                )
                results.append({
                    "success": True,
                    "filename": file.filename,
                    "data": metadata
                })
            except Exception as e:
                results.append({
                    "success": False,
                    "filename": file.filename,
                    "error": str(e)
                })
        
        return JSONResponse(content={
            "user_id": user_id,
            "total": len(files),
            "processed": False,
            "results": results
        })
    
    # Parse languages
    lang_list = [l.strip().lower() for l in languages.split(",")]
    
    # Process all documents and merge
    result = await document_processing_service.process_multiple_documents(
        user_id,
        files,
        document_type
    )
    
    return JSONResponse(content=result)


# ============================================================================
# DOCUMENT RETRIEVAL
# ============================================================================

@router.get("/list/{user_id}")
async def list_user_documents(user_id: str):
    """
    List all documents for a user
    
    Returns:
        List of document files with metadata
    """
    docs_dir = settings.get_user_documents_dir(user_id)
    
    documents = []
    for doc_file in docs_dir.iterdir():
        if doc_file.is_file() and not doc_file.name.endswith('_extracted.json'):
            # Check if extraction exists
            extraction_path = doc_file.parent / f"{doc_file.stem}_extracted.json"
            has_extraction = extraction_path.exists()
            
            # Try to get document type from filename
            doc_type = None
            name_parts = doc_file.stem.split('_')
            if name_parts[0] in ['id_card', 'certificate', 'passport', 'doc']:
                doc_type = name_parts[0]
            
            documents.append({
                "filename": doc_file.name,
                "document_type": doc_type,
                "path": str(doc_file),
                "size": doc_file.stat().st_size,
                "processed": has_extraction,
                "created_at": doc_file.stat().st_ctime
            })
    
    # Sort by creation time (newest first)
    documents.sort(key=lambda x: x["created_at"], reverse=True)
    
    return JSONResponse(content={
        "user_id": user_id,
        "total_documents": len(documents),
        "documents": documents
    })


@router.get("/data/{user_id}/{filename}")
async def get_document_data(user_id: str, filename: str):
    """
    Get the extracted data for a specific document
    
    Args:
        user_id: User identifier
        filename: Document filename
        
    Returns:
        Extracted structured data
    """
    docs_dir = settings.get_user_documents_dir(user_id)
    
    # Find the document
    doc_path = docs_dir / filename
    if not doc_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Find extraction file
    extraction_path = docs_dir / f"{doc_path.stem}_extracted.json"
    if not extraction_path.exists():
        raise HTTPException(
            status_code=404, 
            detail="Document has not been processed. Upload with process=true"
        )
    
    with open(extraction_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return JSONResponse(content={
        "user_id": user_id,
        "filename": filename,
        "data": data
    })


@router.post("/process/{user_id}/{filename}")
async def process_existing_document(
    user_id: str, 
    filename: str,
    document_type: Optional[str] = Query(None),
    languages: str = Query("english,urdu")
):
    """
    Process an already uploaded document that wasn't processed initially
    
    Args:
        user_id: User identifier
        filename: Document filename
        document_type: Optional type hint
        languages: Languages for OCR
        
    Returns:
        Processing result with extracted data
    """
    docs_dir = settings.get_user_documents_dir(user_id)
    doc_path = docs_dir / filename
    
    if not doc_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Parse languages
    lang_list = [l.strip().lower() for l in languages.split(",")]
    
    try:
        # Run OCR
        print(f"\n🔍 Processing existing document: {filename}")
        ocr_result = await document_processing_service.extract_text(
            doc_path, lang_list
        )
        
        # Extract structured data
        extracted = await document_processing_service.extract_structured_data(
            ocr_result, document_type
        )
        
        # Save extraction result
        output_path = docs_dir / f"{doc_path.stem}_extracted.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                "ocr": ocr_result,
                "extracted": extracted,
                "metadata": {
                    "filename": filename,
                    "document_type": document_type
                }
            }, f, indent=2, ensure_ascii=False)
        
        return JSONResponse(content={
            "success": True,
            "user_id": user_id,
            "filename": filename,
            "data": {
                "extracted": extracted,
                "output_path": str(output_path)
            }
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {str(e)}"
        )


# ============================================================================
# USER DATA MANAGEMENT
# ============================================================================

@router.get("/user/{user_id}/all-data")
async def get_all_user_document_data(user_id: str):
    """
    Get all extracted data from all user's documents (merged)
    
    This is useful for form filling - combines all document data.
    
    Returns:
        Merged data from all processed documents
    """
    docs_dir = settings.get_user_documents_dir(user_id)
    
    all_data = {}
    sources = []
    
    # Find all extraction files
    for extraction_file in docs_dir.glob("*_extracted.json"):
        try:
            with open(extraction_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            extracted = data.get("extracted", {})
            
            # Merge data (later documents override earlier ones)
            for key, value in extracted.items():
                if value is not None and key != "error":
                    all_data[key] = value
            
            sources.append(extraction_file.stem.replace("_extracted", ""))
            
        except Exception as e:
            print(f"Error reading {extraction_file}: {e}")
            continue
    
    return JSONResponse(content={
        "user_id": user_id,
        "sources": sources,
        "total_fields": len(all_data),
        "merged_data": all_data
    })


@router.delete("/delete/{user_id}/{filename}")
async def delete_document(user_id: str, filename: str):
    """
    Delete a document and its extraction data
    
    Args:
        user_id: User identifier
        filename: Document filename
        
    Returns:
        Success status
    """
    docs_dir = settings.get_user_documents_dir(user_id)
    doc_path = docs_dir / filename
    
    if not doc_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # Delete document
        doc_path.unlink()
        
        # Delete extraction if exists
        extraction_path = docs_dir / f"{doc_path.stem}_extracted.json"
        if extraction_path.exists():
            extraction_path.unlink()
        
        return JSONResponse(content={
            "success": True,
            "message": f"Document '{filename}' deleted"
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Delete failed: {str(e)}"
        )