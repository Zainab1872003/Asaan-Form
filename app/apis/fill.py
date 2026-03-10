import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from config import settings
from services.document_processing_service import document_processing_service
from services.form_filling_service import form_filling_service
from services.form_pdf_overlay_service import form_pdf_overlay_service
from services.form_processing_service import form_processing_service


router = APIRouter(prefix="/fill", tags=["Filling"])


@router.post("/fill-form")
async def fill_form_endpoint(
    user_id: str = Form(...),
    form_file: UploadFile = File(...),
    document_files: List[UploadFile] = File(...),
    return_pdf: bool = Form(True),
):
    """
    Upload a blank form AND supporting documents (ID, Degrees, etc.).
    Maps document data to form fields and overlays values on the original PDF:
    - Text/date/dropdown: value is drawn to the right of each field label bbox.
    - Checkbox: a checkmark is drawn in the field bbox when value is checked.
    Returns the filled PDF file by default, or JSON only if return_pdf=false.
    """
    try:
        # --- STEP 1: Process Supporting Documents ---
        print(f"Processing {len(document_files)} supporting documents...")
        doc_result = await document_processing_service.process_multiple_documents(
            user_id=user_id,
            files=document_files,
        )
        extracted_user_data = doc_result.get("merged_data", {})

        if not extracted_user_data:
            print("⚠️ Warning: No readable data found in documents.")

        # --- STEP 2: Process the Blank Form ---
        print(f"Processing form template: {form_file.filename}...")
        form_result = await form_processing_service.process_form(
            user_id=user_id,
            file=form_file,
            form_name="auto_process",
        )

        if not form_result["success"]:
            raise HTTPException(
                status_code=400,
                detail=f"Form processing failed: {form_result['errors']}",
            )

        empty_fields = form_result["data"]["form_fields"].get("form_fields", [])

        # --- STEP 3: Map Data to Form ---
        print("Mapping data to form fields...")
        filled_fields = await form_filling_service.fill_form(
            form_fields=empty_fields,
            document_data=extracted_user_data,
        )

        # --- STEP 4: Overlay filled values on the original PDF ---
        form_folder = Path(form_result["data"]["form_folder"])
        original_filename = form_result.get("original_filename") or form_file.filename or "form"
        suffix = Path(original_filename).suffix or ".pdf"
        original_path = form_folder / f"original{suffix}"

        if not original_path.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Original form file not found: {original_path}",
            )

        output_dir = settings.get_user_output_dir(user_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        form_id = form_result["data"]["form_id"]
        filled_pdf_path = output_dir / f"filled_{form_id}.pdf"

        # --- Save field mapping JSON (which form field maps to which value) ---
        mapping = {
            "form_id": form_id,
            "source_data_used": extracted_user_data,
            "field_mapping": [
                {
                    "field_key": f.get("field_key"),
                    "field_name": f.get("field_name"),
                    "field_type": f.get("field_type"),
                    "value": f.get("value"),
                    "page_number": f.get("page_number"),
                }
                for f in filled_fields
            ],
        }
        mapping_path = output_dir / f"filled_{form_id}_mapping.json"
        mapping_path.write_text(json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8")

        page_image_paths = form_result["data"].get("images") or []
        # Docling runs on images rendered from PDF at PDF_DPI; coords are in image space. Scale to PDF points.
        render_dpi = settings.PDF_DPI if (Path(original_path).suffix or "").lower() == ".pdf" else None
        form_pdf_overlay_service.fill_pdf(
            original_path=original_path,
            filled_fields=filled_fields,
            page_image_paths=page_image_paths if page_image_paths else None,
            output_path=filled_pdf_path,
            render_dpi=render_dpi,
        )

        if return_pdf and filled_pdf_path.exists():
            return FileResponse(
                path=str(filled_pdf_path),
                media_type="application/pdf",
                filename=f"filled_{Path(original_filename).stem}.pdf",
            )

        return JSONResponse(
            content={
                "status": "success",
                "message": "Form processed and filled successfully",
                "data": {
                    "filled_fields": filled_fields,
                    "source_data_used": extracted_user_data,
                    "form_metadata": {
                        "pages": form_result["data"]["page_count"],
                        "form_id": form_result["data"]["form_id"],
                    },
                    "filled_pdf_path": str(filled_pdf_path),
                    "mapping_json_path": str(mapping_path),
                },
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))