"""
Document Processing Service - GridFS Compatible 

Architecture rule: AI backend NEVER saves files permanently.
- Receives file bytes from Node.js
- Saves ONLY a temp file during processing (deleted after)
- Returns extracted JSON to Node.js
- Node.js owns ALL storage (GridFS + MongoDB)
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import uuid

from fastapi import UploadFile, HTTPException

from app.config import settings
from app.services.docling_service import DoclingService

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except Exception:
    PDF2IMAGE_AVAILABLE = False
    convert_from_path = None

try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    fitz = None

import httpx
from app.utils.llm import get_llm


class DocumentProcessingService:
    """
    Service for document OCR + data extraction.
    Uses TEMP files only — never permanent disk writes.
    All results returned as JSON to caller (Node.js saves to MongoDB).
    """

    def __init__(self):
        self.llm = get_llm()
        self.docling_service = DoclingService()

    # ========================================================================
    # MAIN PIPELINE — called by document_upload.py API
    # ========================================================================

    async def process_document(
        self,
        user_id: str,
        file: UploadFile,
        document_type: Optional[str] = None,
        languages: List[str] = ["english", "urdu"],
    ) -> Dict:
        """
        Full pipeline:
        1. Write file to a temp location (needed for Docling/OCR tools)
        2. Run OCR / Docling extraction
        3. Run LLM structured extraction
        4. Delete temp file
        5. Return result dict — NO permanent disk write

        The caller (Node.js via document_upload.py) receives this dict and
        saves whatever it needs to MongoDB.
        """
        print("=" * 60)
        print(f"📄 PROCESSING DOCUMENT: {file.filename}")
        print("=" * 60)

        result: Dict = {
            "user_id": user_id,
            "original_filename": file.filename,
            "document_type": document_type,
            "success": False,
            "errors": [],
            "data": {},
        }

        # Read file bytes once
        file_bytes = await file.read()
        if not file_bytes:
            result["errors"].append("Empty file received")
            return result

        file_ext = Path(file.filename or "upload").suffix.lower() or ".pdf"

        # Build a unique temp filename that the AI backend uses internally
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        ai_saved_filename = f"{document_type or 'doc'}_{timestamp}_{unique_id}{file_ext}"

        result["data"]["file_info"] = {
            "original_filename": file.filename,
            "saved_filename": ai_saved_filename,   # Node.js stores this as aiFilename
            "document_type": document_type,
            "size": len(file_bytes),
            "uploaded_at": datetime.now().isoformat(),
        }

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = Path(tmp.name)

        try:
            # Step 1: OCR / text extraction
            ocr_result = await self._extract_text(tmp_path, languages)
            result["data"]["ocr"] = {
                "english_length": len(ocr_result.get("english_text") or ""),
                "urdu_length": len(ocr_result.get("urdu_text") or ""),
                "boxes": ocr_result.get("boxes", []),
            }

            # Step 2: LLM structured extraction
            extracted = await self._extract_structured_data(ocr_result, document_type)
            if "error" in extracted:
                result["errors"].append(extracted["error"])
            else:
                result["data"]["extracted"] = extracted

            result["success"] = len(result["errors"]) == 0

        except Exception as e:
            result["errors"].append(str(e))
            print(f"❌ Document processing error: {e}")
        finally:
            # ALWAYS delete temp file — AI backend owns NO permanent storage
            tmp_path.unlink(missing_ok=True)
            print(f"🗑️  Temp file deleted: {tmp_path.name}")

        print("✅ SUCCESS" if result["success"] else "❌ FAILED")
        return result

    # ========================================================================
    # OCR EXTRACTION
    # ========================================================================

    async def _extract_text(
        self,
        file_path: Path,
        languages: List[str] = ["english", "urdu"],
    ) -> Dict:
        """Extract text from a temp file using Docling (PDF) or OCR microservice (images)."""
        result = {
            "english_text": None,
            "urdu_text": None,
            "combined_text": None,
            "boxes": [],
            "docling_json": None,
        }

        file_ext = file_path.suffix.lower()

        # ── PDF: use Docling ──────────────────────────────────────────────────
        if file_ext == ".pdf":
            print("  📄 PDF detected — using Docling")
            try:
                docling_result = await self.docling_service.process_document(
                    str(file_path), save_outputs=False
                )
                markdown = docling_result.get("markdown", "")
                result["english_text"] = markdown
                result["combined_text"] = markdown
                result["docling_json"] = docling_result.get("json")
                print(f"  ✓ Docling extracted {len(markdown)} chars")
                return result
            except Exception as e:
                print(f"  ⚠️ Docling failed: {e} — falling back to image OCR")

            # Fallback: convert PDF pages to images then OCR
            try:
                images = self._pdf_to_images(file_path)
                all_text: List[str] = []
                for i, img in enumerate(images, 1):
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as t:
                        img.save(t.name, "PNG")
                        t_path = t.name
                    try:
                        text = await self._ocr_image(t_path)
                        if text:
                            all_text.append(f"[Page {i}]\n{text}")
                    finally:
                        Path(t_path).unlink(missing_ok=True)
                result["english_text"] = "\n\n".join(all_text)
                result["combined_text"] = result["english_text"]
            except Exception as e:
                print(f"  ❌ PDF fallback OCR failed: {e}")

        # ── Image: OCR microservice ───────────────────────────────────────────
        else:
            print("  🖼️ Image detected — using OCR microservice")
            if "english" in languages:
                text = await self._ocr_image(str(file_path))
                result["english_text"] = text
                result["combined_text"] = text
            if "urdu" in languages:
                urdu_text = await self._ocr_urdu(str(file_path))
                result["urdu_text"] = urdu_text
                if urdu_text:
                    result["combined_text"] = (result["combined_text"] or "") + "\n\n" + urdu_text

        return result

    async def _ocr_image(self, file_path_str: str) -> str:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "http://localhost:8001/ocr/english",
                    json={"file_path": file_path_str},
                    timeout=60.0,
                )
                if resp.status_code == 200:
                    return resp.json().get("text", "")
        except Exception as e:
            print(f"  ⚠️ English OCR failed: {e}")
        return ""

    async def _ocr_urdu(self, file_path_str: str) -> str:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "http://localhost:8001/ocr/urdu",
                    json={"file_path": file_path_str},
                    timeout=60.0,
                )
                if resp.status_code == 200:
                    return resp.json().get("text", "")
        except Exception as e:
            print(f"  ⚠️ Urdu OCR failed: {e}")
        return ""

    def _pdf_to_images(self, pdf_path: Path):
        """Convert PDF to PIL images using available library."""
        from PIL import Image as PILImage
        if PDF2IMAGE_AVAILABLE:
            try:
                return convert_from_path(str(pdf_path), dpi=settings.PDF_DPI)
            except Exception:
                pass
        if PYMUPDF_AVAILABLE:
            doc = fitz.open(str(pdf_path))
            images = []
            mat = fitz.Matrix(settings.PDF_DPI / 72, settings.PDF_DPI / 72)
            for page in doc:
                pix = page.get_pixmap(matrix=mat)
                img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)
            doc.close()
            return images
        raise HTTPException(status_code=500, detail="No PDF conversion tool available")

    # ========================================================================
    # LLM STRUCTURED EXTRACTION
    # ========================================================================

    async def _extract_structured_data(
        self,
        ocr_result: Dict,
        document_type: Optional[str] = None,
    ) -> Dict:
        text = (
            ocr_result.get("english_text")
            or ocr_result.get("combined_text")
            or ""
        )
        urdu_text = ocr_result.get("urdu_text") or ""

        if not text and not urdu_text:
            return {"error": "No text extracted from document"}

        if text and urdu_text:
            prompt = f"""You are a bilingual document understanding agent.
Document type: {document_type or 'unknown'}

Extract ALL information. Keys must be English snake_case.
Translate Urdu values to English. Use null for missing values.

English text:
{text}

Urdu text:
{urdu_text}

Return ONLY valid JSON."""
        else:
            combined = text or urdu_text
            prompt = f"""Extract structured information from this document.
Document type: {document_type or 'unknown'}

Text:
{combined}

Return ONLY valid JSON with snake_case keys. Translate any Urdu to English."""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
            return json.loads(content)
        except json.JSONDecodeError:
            return {"error": "LLM returned non-JSON response"}
        except Exception as e:
            return {"error": f"LLM extraction failed: {str(e)}"}


# Singleton
document_processing_service = DocumentProcessingService()