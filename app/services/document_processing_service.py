"""
Document Processing Service
Handles document (ID cards, certificates, etc.) processing:
1. Save documents in user's documents folder
2. Run OCR (English + Urdu) on documents
3. Use LLM to extract structured data
4. Return JSON with extracted information

This is SEPARATE from Form Processing - documents provide DATA to fill forms.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import uuid

from fastapi import UploadFile, HTTPException
from PIL import Image

from config import settings
from services.docling_service import DoclingService
from utils.llm import get_llm, generate_response_from_prompt

# Try pdf2image first, fallback to PyMuPDF if needed
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except (ImportError, Exception):
    PDF2IMAGE_AVAILABLE = False
    convert_from_path = None

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    fitz = None
from services.ocr_service import extract_english_text
from services.urdu_ocr_service import extract_urdu_text



class DocumentProcessingService:
    """
    Service for document upload and data extraction
    Documents are ID cards, certificates, etc. that contain DATA to fill forms
    """
    
    def __init__(self):
        self.llm = get_llm()
        self.docling_service = DoclingService()
        self.use_docling_for_pdfs = True  # Use Docling for PDFs (faster, more reliable)
    
    # ========================================================================
    # FILE UPLOAD METHODS
    # ========================================================================
    
    async def save_document(
        self, 
        user_id: str, 
        file: UploadFile,
        document_type: Optional[str] = None
    ) -> Tuple[Path, Dict]:
        """
        Save a document file for a user
        
        Args:
            user_id: User identifier
            file: Uploaded document file
            document_type: Optional type (id_card, certificate, etc.)
            
        Returns:
            Tuple of (file_path, metadata)
        """
        # Create documents directory
        docs_dir = settings.get_user_documents_dir(user_id)
        
        # Create unique filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = uuid.uuid4().hex[:8]
        file_ext = Path(file.filename).suffix.lower()
        
        # Include document type in filename if provided
        if document_type:
            filename = f"{document_type}_{timestamp}_{unique_id}{file_ext}"
        else:
            filename = f"doc_{timestamp}_{unique_id}{file_ext}"
        
        file_path = docs_dir / filename
        
        # Save the file
        content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        metadata = {
            "original_filename": file.filename,
            "saved_filename": filename,
            "file_path": str(file_path),
            "document_type": document_type,
            "size": len(content),
            "uploaded_at": datetime.now().isoformat()
        }
        
        return file_path, metadata
    
    # ========================================================================
    # OCR METHODS
    # ========================================================================
    
    async def extract_text(
        self, 
        file_path: Path,
        languages: List[str] = ["english", "urdu"]
    ) -> Dict:
        """
        Extract text from document using OCR
        Handles both images and PDFs (converts PDF to images first)
        
        Args:
            file_path: Path to the document (image or PDF)
            languages: List of languages to extract ("english", "urdu", or both)
            
        Returns:
            Dict with extracted text for each language
        """
        result = {
            "english_text": None,
            "urdu_text": None,
            "combined_text": None
        }
        
        file_path_str = str(file_path)
        file_ext = file_path.suffix.lower()
        
        # Handle PDF files - use Docling for faster processing
        if file_ext == ".pdf":
            print("  📄 PDF detected...")
            
            # Option 1: Use Docling directly (faster, built-in OCR)
            if self.use_docling_for_pdfs:
                try:
                    print("  Using Docling for PDF OCR (faster)...")
                    docling_result = await self.docling_service.process_document(
                        file_path_str,
                        save_outputs=False
                    )
                    
                    # Extract text from Docling markdown
                    markdown_text = docling_result.get("markdown", "")
                    
                    # For documents, we mainly need the text content
                    if "english" in languages:
                        result["english_text"] = markdown_text
                        print(f"  ✓ Docling OCR: {len(markdown_text)} characters")
                    
                    # Note: Docling doesn't support Urdu OCR, so we skip it for PDFs
                    if "urdu" in languages:
                        print("  ⚠️ Urdu OCR not available for PDFs via Docling")
                        result["urdu_text"] = ""
                    
                    result["combined_text"] = markdown_text
                    return result
                    
                except Exception as docling_error:
                    print("  ⚠️ Docling failed ({str(docling_error)[:100]}), falling back to image-based OCR...")
                    # Fall through to image-based OCR
            
            # Option 2: Convert to images and use PaddleOCR (slower but supports Urdu)
            print("  Converting PDF to images for OCR...")
            try:
                # Try pdf2image first (requires poppler)
                if PDF2IMAGE_AVAILABLE:
                    try:
                        images = convert_from_path(
                            file_path_str,
                            dpi=settings.PDF_DPI,
                            fmt='png'
                        )
                        print(f"  ✓ Converted {len(images)} pages using pdf2image")
                    except Exception as pdf2img_error:
                        # Fallback to PyMuPDF if pdf2image fails
                        if PYMUPDF_AVAILABLE:
                            print(f"  ⚠️ pdf2image failed ({pdf2img_error}), trying PyMuPDF...")
                            images = self._convert_pdf_with_pymupdf(file_path, settings.PDF_DPI)
                            print(f"  ✓ Converted {len(images)} pages using PyMuPDF")
                        else:
                            raise HTTPException(
                                status_code=500,
                                detail=f"PDF conversion failed: {str(pdf2img_error)}. "
                                       f"Please install poppler-utils or ensure PyMuPDF is available."
                            )
                elif PYMUPDF_AVAILABLE:
                    # Use PyMuPDF directly
                    images = self._convert_pdf_with_pymupdf(file_path, settings.PDF_DPI)
                    print(f"  ✓ Converted {len(images)} pages using PyMuPDF")
                else:
                    raise HTTPException(
                        status_code=500,
                        detail="PDF conversion not available. Please install pdf2image (with poppler) or PyMuPDF."
                    )
                
                # Process each page and combine text
                all_english_text = []
                all_urdu_text = []
                
                for i, image in enumerate(images, 1):
                    print(f"  Processing page {i}/{len(images)}...")
                    
                    # Save temporary image for OCR
                    temp_image_path = file_path.parent / f"temp_page_{i}.png"
                    image.save(str(temp_image_path), "PNG")
                    
                    try:
                        # Extract English text with timeout protection
                        if "english" in languages:
                            try:
                                print(f"    Running English OCR on page {i}...")
                                import time
                                start = time.time()
                                
                                page_english = extract_english_text(temp_image_path)
                                
                                elapsed = time.time() - start
                                if elapsed > 60:
                                    print(f"    ⚠️ Page {i} OCR took {elapsed:.1f}s (slow)")
                                
                                if page_english:
                                    all_english_text.append(f"[Page {i}]\n{page_english}")
                                    print(f"    ✓ Page {i} English OCR: {len(page_english)} chars in {elapsed:.1f}s")
                                else:
                                    print(f"    ⚠️ Page {i} English OCR: No text found")
                            except KeyboardInterrupt:
                                raise
                            except Exception as ocr_error:
                                error_msg = str(ocr_error)[:100]
                                print(f"    ❌ Page {i} English OCR failed: {error_msg}")
                                # Continue with other pages - don't fail entire document
                                if "timeout" in error_msg.lower() or "hang" in error_msg.lower():
                                    print("    ⚠️ OCR appears to be hanging, skipping remaining pages...")
                                    break
                        
                        # Extract Urdu text with timeout protection
                        if "urdu" in languages:
                            try:
                                print(f"    Running Urdu OCR on page {i}...")
                                page_urdu = extract_urdu_text(str(temp_image_path))
                                if page_urdu:
                                    all_urdu_text.append(f"[Page {i}]\n{page_urdu}")
                                    print(f"    ✓ Page {i} Urdu OCR: {len(page_urdu)} chars")
                                else:
                                    print(f"    ⚠️ Page {i} Urdu OCR: No text found")
                            except Exception as ocr_error:
                                print(f"    ❌ Page {i} Urdu OCR failed: {str(ocr_error)[:100]}")
                                # Continue with other pages
                    finally:
                        # Clean up temporary image
                        if temp_image_path.exists():
                            temp_image_path.unlink()
                
                # Combine all pages
                if all_english_text:
                    result["english_text"] = "\n\n".join(all_english_text)
                    print(f"  ✓ English OCR: {len(result['english_text'])} characters from {len(images)} pages")
                
                if all_urdu_text:
                    result["urdu_text"] = "\n\n".join(all_urdu_text)
                    print(f"  ✓ Urdu OCR: {len(result['urdu_text'])} characters from {len(images)} pages")
                    
            except Exception as e:
                print(f"  ❌ PDF processing failed: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"PDF processing failed: {str(e)}"
                )
        else:
            # Handle image files directly
            # Extract English text
            if "english" in languages:
                try:
                    english_text = extract_english_text(file_path_str)
                    result["english_text"] = english_text
                    print(f"  ✓ English OCR: {len(english_text)} characters")
                except Exception as e:
                    print(f"  ⚠️ English OCR failed: {e}")
                    result["english_text"] = ""
            
            # Extract Urdu text
            if "urdu" in languages:
                try:
                    urdu_text = extract_urdu_text(file_path_str)
                    result["urdu_text"] = urdu_text
                    print(f"  ✓ Urdu OCR: {len(urdu_text)} characters")
                except Exception as e:
                    print(f"  ⚠️ Urdu OCR failed: {e}")
                    result["urdu_text"] = ""
        
        # Combine texts
        texts = []
        if result["english_text"]:
            texts.append(f"[English]\n{result['english_text']}")
        if result["urdu_text"]:
            texts.append(f"[Urdu]\n{result['urdu_text']}")
        
        result["combined_text"] = "\n\n".join(texts) if texts else ""
        
        return result
    
    def _convert_pdf_with_pymupdf(self, pdf_path: Path, dpi: int = 300) -> List[Image.Image]:
        """
        Convert PDF to images using PyMuPDF (fitz) as fallback
        
        Args:
            pdf_path: Path to PDF file
            dpi: DPI for conversion
            
        Returns:
            List of PIL Image objects
        """
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDF (fitz) is not installed")
        
        doc = fitz.open(str(pdf_path))
        images = []
        
        # Calculate zoom factor for desired DPI (default is 72 DPI)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render page to pixmap
            pix = page.get_pixmap(matrix=mat)
            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        
        doc.close()
        return images
    
    # ========================================================================
    # LLM EXTRACTION METHODS
    # ========================================================================
    
    async def extract_structured_data(
        self, 
        ocr_result: Dict,
        document_type: Optional[str] = None
    ) -> Dict:
        """
        Use LLM to extract structured data from OCR text
        
        Args:
            ocr_result: Dict with english_text and urdu_text
            document_type: Optional hint about document type
            
        Returns:
            Structured JSON with extracted data
        """
        english_text = ocr_result.get("english_text", "")
        urdu_text = ocr_result.get("urdu_text", "")
        
        # Build prompt based on whether we have both languages
        if english_text and urdu_text:
            prompt = self._build_bilingual_prompt(english_text, urdu_text, document_type)
        elif english_text:
            prompt = self._build_english_prompt(english_text, document_type)
        elif urdu_text:
            prompt = self._build_urdu_prompt(urdu_text, document_type)
        else:
            return {"error": "No text extracted from document"}
        
        content = None
        try:
            content = generate_response_from_prompt(self.llm, prompt)
            content = self._clean_json_response(content)
            extracted_data = json.loads(content)
            return extracted_data
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse LLM response as JSON",
                "raw_response": content[:500] if content else None
            }
        except Exception as e:
            return {"error": f"LLM extraction failed: {str(e)}"}
    
    def _build_bilingual_prompt(
        self, 
        english_text: str, 
        urdu_text: str,
        document_type: Optional[str]
    ) -> str:
        """Build prompt for bilingual document extraction"""
        type_hint = f"This is a {document_type}." if document_type else ""
        
        return f"""You are a bilingual document understanding agent.

You are given OCR outputs from the SAME document in both English and Urdu.
{type_hint}

Rules:
- Keys must be in English (snake_case)
- Merge information from BOTH OCRs
- Translate Urdu values to English
- Prefer clearer/more complete values when both exist
- Use null if a value is missing or unreadable
- Extract ALL relevant information (names, dates, IDs, addresses, etc.)

English OCR:
{english_text}

Urdu OCR:
{urdu_text}

Return ONLY valid JSON with the extracted data.
Example format:
{{
  "full_name": "John Doe",
  "father_name": "James Doe",
  "date_of_birth": "1990-01-15",
  "id_number": "12345-6789012-3",
  "address": "123 Main St, City",
  "document_type": "national_id"
}}
"""
    
    def _build_english_prompt(self, english_text: str, document_type: Optional[str]) -> str:
        """Build prompt for English-only document extraction"""
        type_hint = f"This is a {document_type}." if document_type else ""
        
        return f"""You are a document understanding agent.

Convert the following OCR text into clean, structured JSON.
{type_hint}

Rules:
- Use meaningful keys in snake_case
- If a value is missing or unreadable, use null
- Extract ALL relevant information (names, dates, IDs, addresses, etc.)

OCR Text:
{english_text}

Return ONLY valid JSON.
"""
    
    def _build_urdu_prompt(self, urdu_text: str, document_type: Optional[str]) -> str:
        """Build prompt for Urdu-only document extraction"""
        type_hint = f"This is a {document_type}." if document_type else ""
        
        return f"""You are a document understanding agent fluent in Urdu.

Convert the following Urdu OCR text into clean, structured JSON.
{type_hint}

Rules:
- Keys must be in English (snake_case)
- Translate Urdu values to English
- If a value is missing or unreadable, use null
- Extract ALL relevant information

Urdu OCR Text:
{urdu_text}

Return ONLY valid JSON with English keys and translated values.
"""
    
    def _clean_json_response(self, content: str) -> str:
        """Clean LLM response to extract JSON"""
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1].strip()
                if content.startswith(("json", "JSON")):
                    content = content[4:].strip()
        return content
    
    # ========================================================================
    # COMPLETE PROCESSING PIPELINE
    # ========================================================================
    
    async def process_document(
        self, 
        user_id: str, 
        file: UploadFile,
        document_type: Optional[str] = None,
        languages: List[str] = ["english", "urdu"]
    ) -> Dict:
        """
        Complete document processing pipeline:
        1. Save document
        2. Run OCR (English + Urdu)
        3. Extract structured data with LLM
        
        Args:
            user_id: User identifier
            file: Uploaded document file
            document_type: Optional type hint (id_card, certificate, etc.)
            languages: Languages to extract
            
        Returns:
            Complete processing result
        """
        print("\n" + "="*60)
        print("📄 DOCUMENT PROCESSING PIPELINE")
        print("="*60)
        print(f"📄 File: {file.filename}")
        print(f"👤 User: {user_id}")
        print(f"📋 Type: {document_type or 'auto-detect'}")
        print()
        
        result = {
            "user_id": user_id,
            "original_filename": file.filename,
            "document_type": document_type,
            "success": False,
            "errors": [],
            "data": {}
        }
        
        try:
            # Step 1: Save document
            print("📁 Step 1: Saving document...")
            file_path, metadata = await self.save_document(
                user_id, file, document_type
            )
            result["data"]["file_info"] = metadata
            print(f"  ✓ Saved to: {file_path}")
            
            # Step 2: Run OCR
            print("\n🔍 Step 2: Running OCR...")
            ocr_result = await self.extract_text(file_path, languages)
            result["data"]["ocr"] = {
                "english_length": len(ocr_result.get("english_text") or ""),
                "urdu_length": len(ocr_result.get("urdu_text") or ""),
            }
            
            # Step 3: Extract structured data
            print("\n🤖 Step 3: Extracting structured data...")
            extracted_data = await self.extract_structured_data(
                ocr_result, document_type
            )
            
            if "error" in extracted_data:
                result["errors"].append(extracted_data["error"])
                print(f"  ⚠️ {extracted_data['error']}")
            else:
                result["data"]["extracted"] = extracted_data
                print(f"  ✓ Extracted {len(extracted_data)} fields")
            
            # Save extraction result
            output_path = file_path.parent / f"{file_path.stem}_extracted.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "ocr": ocr_result,
                    "extracted": extracted_data,
                    "metadata": metadata
                }, f, indent=2, ensure_ascii=False)
            
            result["data"]["output_path"] = str(output_path)
            result["success"] = len(result["errors"]) == 0
            
            # Print summary
            self._print_summary(result)
            
        except HTTPException:
            raise
        except Exception as e:
            error_msg = str(e)
            result["errors"].append(error_msg)
            print(f"\n❌ Pipeline error: {error_msg}")
        
        return result
    
    def _print_summary(self, result: Dict):
        """Print processing summary"""
        print("\n" + "="*60)
        print("📊 DOCUMENT PROCESSING SUMMARY")
        print("="*60)
        
        if result["success"]:
            print("✅ Status: SUCCESS")
            data = result.get("data", {})
            extracted = data.get("extracted", {})
            print("\n📈 Results:")
            print(f"  • Fields extracted: {len(extracted)}")
            if extracted:
                print(f"  • Sample fields: {list(extracted.keys())[:5]}")
        else:
            print("❌ Status: FAILED")
            print("\n⚠️ Errors:")
            for error in result["errors"]:
                print(f"  • {error}")
        
        print("="*60 + "\n")
    
    # ========================================================================
    # BATCH PROCESSING
    # ========================================================================
    
    async def process_multiple_documents(
        self,
        user_id: str,
        files: List[UploadFile],
        document_type: Optional[str] = None
    ) -> Dict:
        """
        Process multiple documents and merge results
        
        Args:
            user_id: User identifier
            files: List of document files
            document_type: Optional type hint
            
        Returns:
            Combined results from all documents
        """
        results = []
        all_extracted = {}
        
        for i, file in enumerate(files, 1):
            print(f"\n--- Processing document {i}/{len(files)} ---")
            result = await self.process_document(
                user_id, file, document_type
            )
            results.append(result)
            
            # Merge extracted data
            if result["success"] and "extracted" in result.get("data", {}):
                extracted = result["data"]["extracted"]
                for key, value in extracted.items():
                    # Keep non-null values, prefer later documents
                    if value is not None:
                        all_extracted[key] = value
        
        return {
            "user_id": user_id,
            "total_documents": len(files),
            "successful": sum(1 for r in results if r["success"]),
            "individual_results": results,
            "merged_data": all_extracted
        }


# Create singleton instance
document_processing_service = DocumentProcessingService()