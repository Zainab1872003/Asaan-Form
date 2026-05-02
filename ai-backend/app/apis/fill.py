# """
# Fill API Routes - GridFS Compatible Architecture

# All endpoints receive data from Node.js backend.
# AI backend NEVER reads from local disk for form/document data.

# Endpoints:
#   POST /fill/map-document     → Node sends extracted_data JSON + form_id → returns filled_fields JSON
#   POST /fill/fill-pdf         → Node sends filled_fields JSON + form PDF bytes → returns filled PDF bytes
#   POST /fill/map-and-fill-pdf → Node sends extracted_data + form PDF bytes → returns filled PDF bytes
# """

# from __future__ import annotations

# import io
# import json
# import tempfile
# from pathlib import Path
# from typing import Any, Dict, List, Optional

# from fastapi import APIRouter, File, Form, HTTPException, UploadFile
# from fastapi.responses import Response, JSONResponse

# from app.graph.master_graph import master_graph
# from app.schemas.state import AgentState
# from app.services.form_pdf_overlay_service import form_pdf_overlay_service
# from app.config import settings

# import logging
# logger = logging.getLogger(__name__)

# router = APIRouter(prefix="/fill", tags=["Filling"])


# # ============================================================================
# # ENDPOINT 1: MAP DOCUMENT DATA TO FORM FIELDS (returns JSON only)
# # Node.js sends: form_id (AI folder id), extracted_data (JSON), ocr_text (optional)
# # AI returns: filled_fields list with values
# # ============================================================================

# @router.post("/map-document")
# async def map_document_endpoint(
#     user_id: str = Form(...),
#     form_id: str = Form(...),
#     extracted_data: str = Form(...),       # JSON string of extracted document data
#     ocr_text: Optional[str] = Form(""),   # Optional raw OCR text for better matching
# ):
#     """
#     Map extracted document data to form fields using LLM.

#     Node.js sends extracted_data (already stored in MongoDB) to the AI backend.
#     AI returns filled_fields list. Node.js saves this to MongoDB semanticMapping.

#     No local file I/O at all.
#     """
#     print(f"\n📥 MAP-DOCUMENT: user={user_id}, form_id={form_id}")

#     try:
#         extracted_user_data = json.loads(extracted_data)
#     except Exception:
#         raise HTTPException(status_code=400, detail="extracted_data must be valid JSON")

#     try:
#         map_state = AgentState(
#             user_id=user_id,
#             intent="fill",
#             form_id=form_id,
#             document_data=extracted_user_data,
#             document_ocr_text=ocr_text or "",
#             retry_count=0,
#         )
#         graph_result = await master_graph.ainvoke(map_state)

#         if graph_result.get("error"):
#             raise HTTPException(status_code=500, detail=graph_result["error"])

#         filled_fields = graph_result.get("form_result", {}).get("mapping", [])
#         missing_keys = graph_result.get("missing_keys", [])
#         chatbot_prompt = graph_result.get("results", {}).get("chatbot", {})

#         return JSONResponse(content={
#             "success": True,
#             "filled_fields": filled_fields,
#             "missing_keys": missing_keys,
#             "chatbot_initial_prompt": chatbot_prompt,
#         })

#     except HTTPException:
#         raise
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# # ============================================================================
# # ENDPOINT 2: GENERATE FILLED PDF (returns PDF bytes)
# # Node.js sends: filled_fields JSON + original form PDF as file upload
# # AI returns: filled PDF as binary response
# # ============================================================================

# @router.post("/fill-pdf")
# async def fill_pdf_endpoint(
#     user_id: str = Form(...),
#     form_id: str = Form(...),
#     filled_fields: str = Form(...),        # JSON string of filled fields (from MongoDB)
#     form_file: UploadFile = File(...),     # Original blank form PDF
# ):
#     """
#     Overlay filled values on the original form PDF.

#     Node.js streams the original form PDF from GridFS and sends it here.
#     AI overlays text/checkmarks and returns the filled PDF as bytes.
#     No disk reads — everything in memory.
#     """
#     print(f"\n📥 FILL-PDF: user={user_id}, form_id={form_id}, file={form_file.filename}")

#     try:
#         fields = json.loads(filled_fields)
#     except Exception:
#         raise HTTPException(status_code=400, detail="filled_fields must be valid JSON")

#     try:
#         # Read PDF bytes from upload
#         pdf_bytes = await form_file.read()
#         if not pdf_bytes:
#             raise HTTPException(status_code=400, detail="Empty form file received")

#         suffix = Path(form_file.filename or "form.pdf").suffix.lower() or ".pdf"
#         render_dpi = settings.PDF_DPI if suffix == ".pdf" else None

#         # Write to a temp file (PyMuPDF needs a file path)
#         with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
#             tmp_in.write(pdf_bytes)
#             tmp_in_path = Path(tmp_in.name)

#         with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_out:
#             tmp_out_path = Path(tmp_out.name)

#         try:
#             form_pdf_overlay_service.fill_pdf(
#                 original_path=tmp_in_path,
#                 filled_fields=fields,
#                 page_image_paths=None,
#                 output_path=tmp_out_path,
#                 render_dpi=render_dpi,
#             )
#             filled_pdf_bytes = tmp_out_path.read_bytes()
#         finally:
#             tmp_in_path.unlink(missing_ok=True)
#             tmp_out_path.unlink(missing_ok=True)

#         return Response(
#             content=filled_pdf_bytes,
#             media_type="application/pdf",
#             headers={
#                 "Content-Disposition": f'attachment; filename="filled_{form_id}.pdf"',
#                 "Content-Length": str(len(filled_pdf_bytes)),
#             },
#         )

#     except HTTPException:
#         raise
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# # ============================================================================
# # ENDPOINT 3: MAP + FILL IN ONE SHOT (map data then generate PDF)
# # Node.js sends: extracted_data JSON + original form PDF bytes
# # AI returns: filled PDF bytes directly
# # ============================================================================

# @router.post("/map-and-fill-pdf")
# async def map_and_fill_pdf_endpoint(
#     user_id: str = Form(...),
#     form_id: str = Form(...),
#     extracted_data: str = Form(...),       # JSON string of extracted document data
#     ocr_text: Optional[str] = Form(""),
#     form_file: UploadFile = File(...),     # Original blank form PDF from GridFS
# ):
#     """
#     Map document data to form fields AND generate filled PDF in one call.

#     Used when Node.js wants the PDF immediately without a separate map step.
#     Returns both the filled PDF bytes AND the filled_fields JSON
#     (so Node.js can save it to MongoDB).
#     """
#     print(f"\n📥 MAP-AND-FILL-PDF: user={user_id}, form_id={form_id}")

#     try:
#         extracted_user_data = json.loads(extracted_data)
#     except Exception:
#         raise HTTPException(status_code=400, detail="extracted_data must be valid JSON")

#     try:
#         # Step 1: LLM mapping via LangGraph
#         map_state = AgentState(
#             user_id=user_id,
#             intent="fill",
#             form_id=form_id,
#             document_data=extracted_user_data,
#             document_ocr_text=ocr_text or "",
#             retry_count=0,
#         )
#         graph_result = await master_graph.ainvoke(map_state)

#         if graph_result.get("error"):
#             raise HTTPException(status_code=500, detail=graph_result["error"])

#         filled_fields = graph_result.get("form_result", {}).get("mapping", [])
#         missing_keys = graph_result.get("missing_keys", [])

#         # Step 2: PDF overlay
#         pdf_bytes = await form_file.read()
#         if not pdf_bytes:
#             raise HTTPException(status_code=400, detail="Empty form file received")

#         suffix = Path(form_file.filename or "form.pdf").suffix.lower() or ".pdf"
#         render_dpi = settings.PDF_DPI if suffix == ".pdf" else None

#         with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
#             tmp_in.write(pdf_bytes)
#             tmp_in_path = Path(tmp_in.name)

#         with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_out:
#             tmp_out_path = Path(tmp_out.name)

#         try:
#             form_pdf_overlay_service.fill_pdf(
#                 original_path=tmp_in_path,
#                 filled_fields=filled_fields,
#                 page_image_paths=None,
#                 output_path=tmp_out_path,
#                 render_dpi=render_dpi,
#             )
#             filled_pdf_bytes = tmp_out_path.read_bytes()
#         finally:
#             tmp_in_path.unlink(missing_ok=True)
#             tmp_out_path.unlink(missing_ok=True)

#         # Encode filled_fields into response header so Node.js can save it
#         import base64
#         fields_b64 = base64.b64encode(
#             json.dumps(filled_fields, ensure_ascii=False).encode()
#         ).decode()
#         missing_b64 = base64.b64encode(
#             json.dumps(missing_keys, ensure_ascii=False).encode()
#         ).decode()

#         return Response(
#             content=filled_pdf_bytes,
#             media_type="application/pdf",
#             headers={
#                 "Content-Disposition": f'attachment; filename="filled_{form_id}.pdf"',
#                 "Content-Length": str(len(filled_pdf_bytes)),
#                 "X-Filled-Fields": fields_b64,
#                 "X-Missing-Keys": missing_b64,
#             },
#         )

#     except HTTPException:
#         raise
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# # ============================================================================
# # ENDPOINT 4: FILL PDF WITH SAVED MAPPING (skip LLM, use stored fields)
# # Node.js sends: saved filled_fields from MongoDB + form PDF bytes
# # Same as /fill-pdf but kept for backward compatibility naming
# # ============================================================================

# @router.post("/fill-existing")
# async def fill_existing_endpoint(
#     user_id: str = Form(...),
#     form_id: str = Form(...),
#     saved_mapping: str = Form(...),        # JSON string of saved fields from MongoDB
#     form_file: UploadFile = File(...),     # Original blank form PDF from GridFS
# ):
#     """
#     Regenerate filled PDF using a previously saved mapping from MongoDB.
#     Node.js fetches the form PDF from GridFS and sends it here.
#     No local disk I/O.
#     """
#     print(f"\n📥 FILL-EXISTING: user={user_id}, form_id={form_id}")

#     try:
#         fields = json.loads(saved_mapping)
#     except Exception:
#         raise HTTPException(status_code=400, detail="saved_mapping must be valid JSON")

#     try:
#         pdf_bytes = await form_file.read()
#         if not pdf_bytes:
#             raise HTTPException(status_code=400, detail="Empty form file received")

#         suffix = Path(form_file.filename or "form.pdf").suffix.lower() or ".pdf"
#         render_dpi = settings.PDF_DPI if suffix == ".pdf" else None

#         with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
#             tmp_in.write(pdf_bytes)
#             tmp_in_path = Path(tmp_in.name)

#         with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_out:
#             tmp_out_path = Path(tmp_out.name)

#         try:
#             form_pdf_overlay_service.fill_pdf(
#                 original_path=tmp_in_path,
#                 filled_fields=fields,
#                 page_image_paths=None,
#                 output_path=tmp_out_path,
#                 render_dpi=render_dpi,
#             )
#             filled_pdf_bytes = tmp_out_path.read_bytes()
#         finally:
#             tmp_in_path.unlink(missing_ok=True)
#             tmp_out_path.unlink(missing_ok=True)

#         return Response(
#             content=filled_pdf_bytes,
#             media_type="application/pdf",
#             headers={
#                 "Content-Disposition": f'attachment; filename="filled_{form_id}.pdf"',
#                 "Content-Length": str(len(filled_pdf_bytes)),
#             },
#         )

#     except HTTPException:
#         raise
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


"""
Fill API Routes - GridFS Compatible Architecture
AI backend NEVER reads from local disk.

FIXED: /map-document no longer crashes when extracted_data is empty.
       Returns form schema with null values so frontend still works.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, JSONResponse

from app.graph.master_graph import master_graph
from app.schemas.state import AgentState
from app.services.form_pdf_overlay_service import form_pdf_overlay_service
from app.services.form_processing_service import form_processing_service
from app.config import settings

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fill", tags=["Filling"])


# ── shared helper ─────────────────────────────────────────────────────────────
def _get_empty_fields_for_form(user_id: str, form_id: str):
    """Load form schema and return fields with null values."""
    try:
        form_result = form_processing_service.get_form_result(user_id, form_id)
        raw_fields = form_result.get("form_fields", {}).get("form_fields", [])
        return [dict(f, value=None) for f in raw_fields]
    except Exception:
        return []


def _do_pdf_overlay(pdf_bytes: bytes, filename: str, fields: list) -> bytes:
    """Write temp files, run overlay, return filled PDF bytes, delete temps."""
    suffix = Path(filename or "form.pdf").suffix.lower() or ".pdf"
    render_dpi = settings.PDF_DPI if suffix == ".pdf" else None

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
        tmp_in.write(pdf_bytes)
        tmp_in_path = Path(tmp_in.name)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_out:
        tmp_out_path = Path(tmp_out.name)

    try:
        form_pdf_overlay_service.fill_pdf(
            original_path=tmp_in_path,
            filled_fields=fields,
            page_image_paths=None,
            output_path=tmp_out_path,
            render_dpi=render_dpi,
        )
        return tmp_out_path.read_bytes()
    finally:
        tmp_in_path.unlink(missing_ok=True)
        tmp_out_path.unlink(missing_ok=True)


# =============================================================================
# ENDPOINT 1: MAP DOCUMENT DATA → FORM FIELDS  (JSON only, no PDF)
# =============================================================================
@router.post("/map-document")
async def map_document_endpoint(
    user_id: str = Form(...),
    form_id: str = Form(...),
    extracted_data: str = Form(...),
    ocr_text: Optional[str] = Form(""),
):
    """
    Map extracted document data to form fields using LLM.
    If extracted_data is empty, returns form schema with null values instead of crashing.
    """
    print(f"\n📥 MAP-DOCUMENT: user={user_id}, form_id={form_id}")

    try:
        extracted_user_data = json.loads(extracted_data)
    except Exception:
        raise HTTPException(status_code=400, detail="extracted_data must be valid JSON")

    # ── Empty data: return blank form schema, don't crash ────────────────────
    if not extracted_user_data:
        print("  ⚠️ No extracted data — returning blank form schema")
        empty_fields = _get_empty_fields_for_form(user_id, form_id)
        return JSONResponse(content={
            "success": True,
            "filled_fields": empty_fields,
            "missing_keys": empty_fields,
            "chatbot_initial_prompt": {},
            "warning": "No document data extracted. Fill fields manually or re-upload a clearer document.",
        })

    # ── Normal: run LLM mapping via LangGraph ────────────────────────────────
    try:
        map_state = AgentState(
            user_id=user_id,
            intent="fill",
            form_id=form_id,
            document_data=extracted_user_data,
            document_ocr_text=ocr_text or "",
            retry_count=0,
        )
        graph_result = await master_graph.ainvoke(map_state)

        if graph_result.get("error"):
            raise HTTPException(status_code=500, detail=graph_result["error"])

        filled_fields = graph_result.get("form_result", {}).get("mapping", [])
        missing_keys  = graph_result.get("missing_keys", [])
        chatbot_prompt = graph_result.get("results", {}).get("chatbot", {})

        # Safety fallback if LLM returned nothing
        if not filled_fields:
            print("  ⚠️ LLM returned no mapping — using blank schema")
            filled_fields = _get_empty_fields_for_form(user_id, form_id)

        return JSONResponse(content={
            "success": True,
            "filled_fields": filled_fields,
            "missing_keys": missing_keys,
            "chatbot_initial_prompt": chatbot_prompt,
        })

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENDPOINT 2: GENERATE FILLED PDF  (overlay only, no LLM)
# Node sends filled_fields JSON + form PDF bytes
# =============================================================================
@router.post("/fill-pdf")
async def fill_pdf_endpoint(
    user_id: str = Form(...),
    form_id: str = Form(...),
    filled_fields: str = Form(...),
    form_file: UploadFile = File(...),
):
    print(f"\n📥 FILL-PDF: user={user_id}, form_id={form_id}")

    try:
        fields = json.loads(filled_fields)
    except Exception:
        raise HTTPException(status_code=400, detail="filled_fields must be valid JSON")

    try:
        pdf_bytes = await form_file.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Empty form file received")

        filled_pdf_bytes = _do_pdf_overlay(pdf_bytes, form_file.filename or "form.pdf", fields)

        return Response(
            content=filled_pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="filled_{form_id}.pdf"',
                "Content-Length": str(len(filled_pdf_bytes)),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENDPOINT 3: FILL PDF WITH SAVED MAPPING  (skip LLM, use stored fields)
# Node sends saved_mapping JSON + form PDF bytes from GridFS
# =============================================================================
@router.post("/fill-existing")
async def fill_existing_endpoint(
    user_id: str = Form(...),
    form_id: str = Form(...),
    saved_mapping: str = Form(...),
    form_file: UploadFile = File(...),
):
    print(f"\n📥 FILL-EXISTING: user={user_id}, form_id={form_id}")

    try:
        fields = json.loads(saved_mapping)
    except Exception:
        raise HTTPException(status_code=400, detail="saved_mapping must be valid JSON")

    try:
        pdf_bytes = await form_file.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Empty form file received")

        filled_pdf_bytes = _do_pdf_overlay(pdf_bytes, form_file.filename or "form.pdf", fields)

        return Response(
            content=filled_pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="filled_{form_id}.pdf"',
                "Content-Length": str(len(filled_pdf_bytes)),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))