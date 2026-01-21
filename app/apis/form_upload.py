"""
Form Upload API Routes
Handles form template upload and field extraction.

Forms define WHERE to fill data (fields with coordinates).
This is SEPARATE from document processing.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from pathlib import Path

from app.config import settings
from app.services.form_processing_service import form_processing_service

router = APIRouter(prefix="/form", tags=["Forms"])


# ============================================================================
# FORM UPLOAD AND PROCESSING
# ============================================================================

@router.post("/upload/{user_id}")
async def upload_form(
    user_id: str, 
    file: UploadFile = File(...),
    form_name: Optional[str] = Query(
        None, 
        description="Optional name for the form"
    ),
    process: bool = Query(
        True, 
        description="Whether to process the form immediately"
    )
):
    """
    Upload and process a form template
    
    - Saves form in user's forms folder
    - If PDF: converts to 300 DPI images
    - Processes with Docling to get structure
    - Extracts form fields with coordinates using LLM
    
    Args:
        user_id: User identifier
        file: Form file (PDF, PNG, JPG, JPEG)
        form_name: Optional name for the form
        process: Whether to process immediately (default: True)
        
    Returns:
        Processing result with extracted form fields
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file_ext}'. Allowed: {settings.ALLOWED_EXTENSIONS}"
        )
    
    try:
        if process:
            # Run complete processing pipeline
            result = await form_processing_service.process_form(
                user_id, file, form_name
            )
            return JSONResponse(content=result)
        else:
            # Just save the form without processing
            form_folder, image_paths = await form_processing_service.save_form(
                user_id, file, form_name
            )
            
            return JSONResponse(content={
                "message": "Form saved successfully",
                "user_id": user_id,
                "form_id": form_folder.name,
                "form_folder": str(form_folder),
                "page_count": len(image_paths),
                "images": [str(p) for p in image_paths],
                "processed": False
            })
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload/{user_id}/batch")
async def upload_multiple_forms(
    user_id: str, 
    files: List[UploadFile] = File(...),
    process: bool = Query(True)
):
    """
    Upload multiple forms at once
    
    Args:
        user_id: User identifier
        files: List of form files
        process: Whether to process each form
        
    Returns:
        Results for each uploaded form
    """
    results = []
    
    for file in files:
        try:
            if process:
                result = await form_processing_service.process_form(user_id, file)
            else:
                form_folder, image_paths = await form_processing_service.save_form(
                    user_id, file
                )
                result = {
                    "success": True,
                    "original_filename": file.filename,
                    "form_id": form_folder.name,
                    "page_count": len(image_paths),
                    "processed": False
                }
            
            results.append(result)
            
        except Exception as e:
            results.append({
                "success": False,
                "original_filename": file.filename,
                "error": str(e)
            })
    
    return JSONResponse(content={
        "user_id": user_id,
        "total_forms": len(files),
        "successful": sum(1 for r in results if r.get("success", False)),
        "results": results
    })


# ============================================================================
# FORM RETRIEVAL
# ============================================================================

@router.get("/list/{user_id}")
async def list_user_forms(user_id: str):
    """
    List all forms for a user
    
    Returns:
        List of form folders with their info
    """
    forms = form_processing_service.list_user_forms(user_id)
    
    return JSONResponse(content={
        "user_id": user_id,
        "total_forms": len(forms),
        "forms": forms
    })


@router.get("/fields/{user_id}/{form_id}")
async def get_form_fields(user_id: str, form_id: str):
    """
    Get the extracted fields for a specific form
    
    Args:
        user_id: User identifier
        form_id: Form folder name
        
    Returns:
        Form fields with coordinates and types
    """
    try:
        result = form_processing_service.get_form_result(user_id, form_id)
        
        return JSONResponse(content={
            "success": True,
            "user_id": user_id,
            "form_id": form_id,
            "data": result
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process/{user_id}/{form_id}")
async def process_existing_form(user_id: str, form_id: str):
    """
    Process an already uploaded form that wasn't processed initially
    
    Args:
        user_id: User identifier
        form_id: Form folder name
        
    Returns:
        Processing results with extracted fields
    """
    form_folder = settings.get_user_forms_dir(user_id) / form_id
    
    if not form_folder.exists():
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Get image paths
    image_paths = sorted(form_folder.glob("page_*.png"))
    if not image_paths:
        raise HTTPException(
            status_code=400, 
            detail="No processed images found in form folder"
        )
    
    # Create output directory
    output_dir = form_folder / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Process with Docling
        print(f"\n📄 Processing existing form: {form_id}")
        docling_result = await form_processing_service.process_images_with_docling(
            image_paths, 
            output_dir
        )
        
        # Extract fields with LLM (JSON only, no markdown)
        llm_result = await form_processing_service.extract_form_fields(
            docling_result["json"],
            output_dir
        )
        
        fields = llm_result["fields"]
        
        return JSONResponse(content={
            "success": True,
            "user_id": user_id,
            "form_id": form_id,
            "data": {
                "page_count": docling_result["page_count"],
                "field_count": len(fields.get("form_fields", [])),
                "form_fields": fields,
                "output_paths": {
                    "fields": llm_result["path"],
                    "markdown": docling_result["paths"]["markdown"],
                    "structure": docling_result["paths"]["json"]
                }
            }
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Processing failed: {str(e)}"
        )


# ============================================================================
# FORM FIELD DETAILS
# ============================================================================

@router.get("/field-types/{user_id}/{form_id}")
async def get_form_field_types(user_id: str, form_id: str):
    """
    Get a summary of field types in a form
    
    Returns:
        Count of each field type
    """
    try:
        result = form_processing_service.get_form_result(user_id, form_id)
        fields = result.get("form_fields", {}).get("form_fields", [])
        
        # Count by type
        type_counts = {}
        for field in fields:
            field_type = field.get("field_type", "unknown")
            type_counts[field_type] = type_counts.get(field_type, 0) + 1
        
        return JSONResponse(content={
            "user_id": user_id,
            "form_id": form_id,
            "total_fields": len(fields),
            "field_types": type_counts
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/special-areas/{user_id}/{form_id}")
async def get_form_special_areas(user_id: str, form_id: str):
    """
    Get special areas in a form (signature, photo, etc.)
    
    Returns:
        List of special areas with their requirements
    """
    try:
        result = form_processing_service.get_form_result(user_id, form_id)
        fields = result.get("form_fields", {})
        
        return JSONResponse(content={
            "user_id": user_id,
            "form_id": form_id,
            "special_areas": fields.get("special_areas", []),
            "instructions": fields.get("instructions", [])
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# FORM MANAGEMENT
# ============================================================================

@router.delete("/delete/{user_id}/{form_id}")
async def delete_form(user_id: str, form_id: str):
    """
    Delete a form and all its data
    
    Args:
        user_id: User identifier
        form_id: Form folder name
        
    Returns:
        Success status
    """
    import shutil
    
    form_folder = settings.get_user_forms_dir(user_id) / form_id
    
    if not form_folder.exists():
        raise HTTPException(status_code=404, detail="Form not found")
    
    try:
        shutil.rmtree(form_folder)
        
        return JSONResponse(content={
            "success": True,
            "message": f"Form '{form_id}' deleted"
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Delete failed: {str(e)}"
        )


@router.get("/images/{user_id}/{form_id}")
async def get_form_images(user_id: str, form_id: str):
    """
    Get the list of page images for a form
    
    Returns:
        List of image paths
    """
    form_folder = settings.get_user_forms_dir(user_id) / form_id
    
    if not form_folder.exists():
        raise HTTPException(status_code=404, detail="Form not found")
    
    images = sorted(form_folder.glob("page_*.png"))
    
    return JSONResponse(content={
        "user_id": user_id,
        "form_id": form_id,
        "page_count": len(images),
        "images": [str(img) for img in images]
    })
