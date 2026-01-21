"""
Form Processing Service
Handles FORM processing (not documents):
1. Save form in user's forms folder
2. Convert PDF to 300 DPI images
3. Process images with Docling to get JSON and Markdown
4. Combine responses from all pages
5. Pass to LLM in chunks (to avoid token limits)
6. Merge LLM responses to get final JSON with fields, coordinates, and types

This is SEPARATE from Document Processing - forms define WHERE to fill data.
Documents (processed separately) provide WHAT data to fill.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import uuid

from fastapi import UploadFile, HTTPException
from PIL import Image
from langchain_core.documents import Document

from app.config import settings
from app.services.docling_service import DoclingService
from app.services.llm_service import FormExtractionService

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


class FormProcessingService:
    """
    Service for form upload and field extraction
    Forms are templates that define fillable fields with coordinates
    """
    
    def __init__(self):
        self.docling_service = DoclingService()
        self.llm_service = FormExtractionService()
    
    # ========================================================================
    # FILE UPLOAD METHODS
    # ========================================================================
    
    async def save_form(
        self, 
        user_id: str, 
        file: UploadFile,
        form_name: Optional[str] = None
    ) -> Tuple[Path, List[Path]]:
        """
        Save an uploaded form file
        - If PDF: convert to 300 DPI images
        - If image: save directly
        
        Args:
            user_id: User identifier
            file: Uploaded form file
            form_name: Optional name for the form
            
        Returns:
            Tuple of (form_folder_path, list_of_image_paths)
        """
        # Create unique folder for this form
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        form_id = f"{timestamp}_{uuid.uuid4().hex[:8]}"
        
        if form_name:
            form_id = f"{form_name}_{form_id}"
        
        form_folder = settings.get_user_forms_dir(user_id) / form_id
        form_folder.mkdir(parents=True, exist_ok=True)
        
        # Get file extension
        file_extension = Path(file.filename).suffix.lower()
        
        # Validate file type
        if file_extension not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed: {settings.ALLOWED_EXTENSIONS}"
            )
        
        # Save the original file
        original_filename = f"original{file_extension}"
        original_path = form_folder / original_filename
        
        content = await file.read()
        with open(original_path, "wb") as buffer:
            buffer.write(content)
        
        # Save metadata
        metadata = {
            "form_id": form_id,
            "form_name": form_name,
            "original_filename": file.filename,
            "user_id": user_id,
            "uploaded_at": datetime.now().isoformat()
        }
        
        metadata_path = form_folder / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Convert PDF to images if needed
        if file_extension == ".pdf":
            image_paths = self._pdf_to_images(original_path, form_folder)
            return form_folder, image_paths
        else:
            # For images, ensure good quality
            processed_path = self._ensure_image_quality(original_path, form_folder)
            return form_folder, [processed_path]
    
    def _pdf_to_images(self, pdf_path: Path, output_folder: Path) -> List[Path]:
        """
        Convert PDF to 300 DPI images
        
        Args:
            pdf_path: Path to the PDF file
            output_folder: Folder to save images
            
        Returns:
            List of image paths
        """
        try:
            print(f"  Converting PDF to images at {settings.PDF_DPI} DPI...")
            
            # Try pdf2image first (requires poppler)
            if PDF2IMAGE_AVAILABLE:
                try:
                    images = convert_from_path(
                        str(pdf_path), 
                        dpi=settings.PDF_DPI,
                        fmt='png'
                    )
                    print(f"  ✓ Using pdf2image for conversion")
                except Exception as pdf2img_error:
                    # Fallback to PyMuPDF if pdf2image fails
                    if PYMUPDF_AVAILABLE:
                        print(f"  ⚠️ pdf2image failed ({str(pdf2img_error)[:50]}), trying PyMuPDF...")
                        images = self._convert_pdf_with_pymupdf(pdf_path, settings.PDF_DPI)
                        print(f"  ✓ Using PyMuPDF for conversion")
                    else:
                        raise HTTPException(
                            status_code=500,
                            detail=f"PDF conversion failed: {str(pdf2img_error)}. "
                                   f"Please install poppler-utils or ensure PyMuPDF is available."
                        )
            elif PYMUPDF_AVAILABLE:
                # Use PyMuPDF directly
                images = self._convert_pdf_with_pymupdf(pdf_path, settings.PDF_DPI)
                print(f"  ✓ Using PyMuPDF for conversion")
            else:
                raise HTTPException(
                    status_code=500,
                    detail="PDF conversion not available. Please install pdf2image (with poppler) or PyMuPDF."
                )
            
            saved_images = []
            for i, image in enumerate(images, 1):
                image_path = output_folder / f"page_{i:03d}.png"
                image.save(str(image_path), "PNG")
                saved_images.append(image_path)
                print(f"    ✓ Page {i} saved")
            
            print(f"  ✓ Converted {len(saved_images)} pages")
            return saved_images
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"PDF conversion failed: {str(e)}"
            )
    
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
    
    def _ensure_image_quality(self, image_path: Path, output_folder: Path) -> Path:
        """
        Ensure image has good quality for processing
        
        Args:
            image_path: Path to the image
            output_folder: Folder to save processed image
            
        Returns:
            Path to processed image
        """
        try:
            image = Image.open(image_path)
            
            # Save with 300 DPI metadata
            output_path = output_folder / "page_001.png"
            image.save(
                str(output_path), 
                "PNG",
                dpi=(settings.PDF_DPI, settings.PDF_DPI)
            )
            
            return output_path
            
        except Exception as e:
            print(f"  ⚠️ Image processing warning: {e}")
            return image_path
    
    # ========================================================================
    # DOCLING PROCESSING METHODS
    # ========================================================================
    
    async def process_images_with_docling(
        self, 
        image_paths: List[Path],
        output_dir: Path
    ) -> Dict:
        """
        Process all form images with Docling and combine results
        
        Args:
            image_paths: List of image paths to process
            output_dir: Directory to save outputs
            
        Returns:
            Combined result with markdown and JSON from all pages
        """
        all_markdowns = []
        all_jsons = []
        page_count = 0
        
        print(f"\n📄 Processing {len(image_paths)} page(s) with Docling...")
        
        for i, image_path in enumerate(image_paths, 1):
            print(f"  Page {i}/{len(image_paths)}: {image_path.name}")
            
            try:
                # Process without saving individual files
                result = await self.docling_service.process_document(
                    str(image_path),
                    save_outputs=False
                )
                
                all_markdowns.append({
                    "page": i,
                    "content": result["markdown"]
                })
                
                # Add page number to JSON
                json_with_page = result["json"]
                json_with_page["_page_number"] = i
                all_jsons.append(json_with_page)
                
                page_count += result.get("page_count", 1)
                
            except Exception as e:
                print(f"    ❌ Error: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        if not all_markdowns:
            raise HTTPException(
                status_code=500,
                detail="Failed to process any pages with Docling"
            )
        
        # Combine all results
        combined_markdown = self._combine_markdowns(all_markdowns)
        combined_json = self._combine_jsons(all_jsons)
        
        # Save combined outputs
        markdown_path = output_dir / "form_content.md"
        markdown_path.write_text(combined_markdown, encoding='utf-8')
        
        json_path = output_dir / "form_structure.json"
        json_path.write_text(
            json.dumps(combined_json, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        
        print(f"  ✓ Combined {len(all_markdowns)} pages")
        
        return {
            "markdown": combined_markdown,
            "json": combined_json,
            "page_count": page_count,
            "paths": {
                "markdown": str(markdown_path),
                "json": str(json_path)
            }
        }
    
    def _combine_markdowns(self, markdowns: List[Dict]) -> str:
        """Combine multiple markdown outputs into one"""
        combined = []
        for md in markdowns:
            combined.append(f"\n\n---\n## Page {md['page']}\n---\n\n")
            combined.append(md['content'])
        return "".join(combined)
    
    def _combine_jsons(self, jsons: List[Dict]) -> Dict:
        """Combine multiple JSON outputs into one"""
        combined = {
            "pages": [],
            "all_texts": [],
            "metadata": {
                "total_pages": len(jsons),
                "processed_at": datetime.now().isoformat()
            }
        }
        
        for page_json in jsons:
            page_num = page_json.get("_page_number", 0)
            
            # Store full page data
            combined["pages"].append({
                "page_number": page_num,
                "data": page_json
            })
            
            # Extract texts with page info
            if "texts" in page_json:
                for text_item in page_json["texts"]:
                    text_item["_page"] = page_num
                    combined["all_texts"].append(text_item)
        
        return combined
    
    # ========================================================================
    # LLM FIELD EXTRACTION
    # ========================================================================
    
    async def extract_form_fields(
        self, 
        docling_json: Dict,
        output_dir: Path
    ) -> Dict:
        """
        Extract form fields using LLM with chunking support (JSON only, no markdown)
        
        Args:
            docling_json: Combined JSON with bounding boxes
            output_dir: Directory to save outputs
            
        Returns:
            Extracted fields with coordinates and types
        """
        print(f"\n🤖 Extracting form fields with LLM (JSON only)...")
        
        # Use the LLM service which handles chunking
        extracted_fields = await self.llm_service.extract_fields(
            docling_json
        )
        
        # Save the extracted fields
        fields_path = output_dir / "form_fields.json"
        fields_path.write_text(
            json.dumps(extracted_fields, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        
        field_count = len(extracted_fields.get('form_fields', []))
        print(f"  ✓ Extracted {field_count} fields")
        print(f"  ✓ Saved to: {fields_path}")
        
        return {
            "fields": extracted_fields,
            "path": str(fields_path)
        }
    
    # ========================================================================
    # COMPLETE PROCESSING PIPELINE
    # ========================================================================
    
    async def process_form(
        self, 
        user_id: str, 
        file: UploadFile,
        form_name: Optional[str] = None
    ) -> Dict:
        """
        Complete form processing pipeline:
        1. Save form (convert PDF to images if needed)
        2. Process all pages with Docling
        3. Combine Docling outputs
        4. Extract fields with LLM
        5. Return final result with fields, coordinates, and types
        
        Args:
            user_id: User identifier
            file: Uploaded form file
            form_name: Optional name for the form
            
        Returns:
            Complete processing result
        """
        print("\n" + "="*60)
        print("📋 FORM PROCESSING PIPELINE")
        print("="*60)
        print(f"📄 File: {file.filename}")
        print(f"👤 User: {user_id}")
        print(f"📝 Name: {form_name or 'auto'}")
        print()
        
        result = {
            "user_id": user_id,
            "original_filename": file.filename,
            "form_name": form_name,
            "success": False,
            "errors": [],
            "data": {}
        }
        
        try:
            # Step 1: Save form and convert PDF to images
            print("📁 Step 1: Saving form...")
            form_folder, image_paths = await self.save_form(
                user_id, file, form_name
            )
            
            result["data"]["form_id"] = form_folder.name
            result["data"]["form_folder"] = str(form_folder)
            result["data"]["page_count"] = len(image_paths)
            result["data"]["images"] = [str(p) for p in image_paths]
            
            print(f"  ✓ {len(image_paths)} page(s) ready")
            
            # Step 2: Create output directory
            output_dir = form_folder / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Step 3: Process images with Docling
            print("\n📄 Step 2: Processing with Docling...")
            docling_result = await self.process_images_with_docling(
                image_paths, 
                output_dir
            )
            
            result["data"]["docling"] = {
                "markdown_path": docling_result["paths"]["markdown"],
                "json_path": docling_result["paths"]["json"]
            }
            
            # Step 4: Extract fields with LLM (JSON only, no markdown)
            print("\n🤖 Step 3: Extracting form fields...")
            llm_result = await self.extract_form_fields(
                docling_result["json"],
                output_dir
            )
            
            fields = llm_result["fields"]
            result["data"]["extraction"] = {
                "fields_path": llm_result["path"],
                "field_count": len(fields.get("form_fields", [])),
                "instructions_count": len(fields.get("instructions", [])),
                "special_areas_count": len(fields.get("special_areas", []))
            }
            result["data"]["form_fields"] = fields
            
            # Mark as success
            result["success"] = True
            
            # Print summary
            self._print_summary(result)
            
        except HTTPException:
            raise
        except Exception as e:
            error_msg = str(e)
            result["errors"].append(error_msg)
            print(f"\n❌ Pipeline error: {error_msg}")
            import traceback
            traceback.print_exc()
        
        return result
    
    def _print_summary(self, result: Dict):
        """Print processing summary"""
        print("\n" + "="*60)
        print("📊 FORM PROCESSING SUMMARY")
        print("="*60)
        
        if result["success"]:
            print("✅ Status: SUCCESS")
            data = result["data"]
            extraction = data.get("extraction", {})
            print(f"\n📈 Results:")
            print(f"  • Form ID: {data.get('form_id', 'N/A')}")
            print(f"  • Pages: {data.get('page_count', 0)}")
            print(f"  • Fields found: {extraction.get('field_count', 0)}")
            print(f"  • Instructions: {extraction.get('instructions_count', 0)}")
            print(f"  • Special areas: {extraction.get('special_areas_count', 0)}")
            print(f"\n📁 Output: {data.get('form_folder', 'N/A')}/output/")
        else:
            print("❌ Status: FAILED")
            print(f"\n⚠️ Errors:")
            for error in result["errors"]:
                print(f"  • {error}")
        
        print("="*60 + "\n")
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def get_form_result(self, user_id: str, form_id: str) -> Dict:
        """
        Get the processing result for a specific form
        
        Args:
            user_id: User identifier
            form_id: Form folder name
            
        Returns:
            Form fields and processing outputs
        """
        form_folder = settings.get_user_forms_dir(user_id) / form_id
        
        if not form_folder.exists():
            raise HTTPException(status_code=404, detail="Form not found")
        
        output_dir = form_folder / "output"
        if not output_dir.exists():
            raise HTTPException(
                status_code=404, 
                detail="Form has not been processed yet"
            )
        
        # Read the extracted fields
        fields_path = output_dir / "form_fields.json"
        if not fields_path.exists():
            raise HTTPException(
                status_code=404, 
                detail="Form fields not found"
            )
        
        with open(fields_path, 'r', encoding='utf-8') as f:
            fields = json.load(f)
        
        # Read metadata if exists
        metadata_path = form_folder / "metadata.json"
        metadata = {}
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
        
        return {
            "form_id": form_id,
            "metadata": metadata,
            "form_fields": fields,
            "output_paths": {
                "fields": str(fields_path),
                "markdown": str(output_dir / "form_content.md"),
                "structure": str(output_dir / "form_structure.json")
            }
        }
    
    def list_user_forms(self, user_id: str) -> List[Dict]:
        """
        List all forms for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            List of form info
        """
        forms_dir = settings.get_user_forms_dir(user_id)
        
        forms = []
        for form_folder in forms_dir.iterdir():
            if form_folder.is_dir():
                # Check if processed
                output_dir = form_folder / "output"
                has_output = output_dir.exists()
                
                # Get metadata
                metadata_path = form_folder / "metadata.json"
                metadata = {}
                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                
                # Count images
                images = list(form_folder.glob("page_*.png"))
                
                forms.append({
                    "form_id": form_folder.name,
                    "form_name": metadata.get("form_name"),
                    "original_filename": metadata.get("original_filename"),
                    "page_count": len(images),
                    "processed": has_output,
                    "uploaded_at": metadata.get("uploaded_at"),
                    "path": str(form_folder)
                })
        
        # Sort by upload time (newest first)
        forms.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
        
        return forms


# Create singleton instance
form_processing_service = FormProcessingService()
