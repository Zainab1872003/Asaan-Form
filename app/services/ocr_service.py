# app/services/ocr_service.py
import cv2
import numpy as np
from pathlib import Path
from typing import List
from paddleocr import PaddleOCR
from pdf2image import convert_from_path
import threading

_ocr_instance = None
_ocr_lock = threading.Lock()
_ocr_initializing = False

def get_ocr():
    """
    Get or create PaddleOCR instance (singleton pattern with thread safety)
    """
    global _ocr_instance, _ocr_initializing
    
    if _ocr_instance is not None:
        return _ocr_instance
    
    with _ocr_lock:
        # Double-check pattern
        if _ocr_instance is not None:
            return _ocr_instance
        
        if not _ocr_initializing:
            _ocr_initializing = True
            print("  ⏳ Initializing PaddleOCR (this may take 30-60 seconds on first run)...")
            try:
                # Use lighter models for faster initialization
                _ocr_instance = PaddleOCR(
                    # use_textline_orientation=True,
                    lang="en",
                    enable_mkldnn=False,
                    # use_angle_cls=False,  # Disable angle classification for speed
                    # show_log=False  # Reduce logging overhead
                )
                print("  ✓ PaddleOCR initialized successfully")
            except Exception as e:
                print(f"  ❌ PaddleOCR initialization failed: {e}")
                raise
            finally:
                _ocr_initializing = False
    
    return _ocr_instance

def preload_ocr():
    """
    Preload OCR instance in background to avoid blocking first request
    Call this at application startup
    """
    def _preload():
        try:
            get_ocr()
        except Exception as e:
            print(f"Warning: Failed to preload OCR: {e}")
    
    # Start preloading in background thread
    thread = threading.Thread(target=_preload, daemon=True)
    thread.start()
    return thread

def load_input(path: Path) -> np.ndarray:
    """
    Load image from file path
    
    Args:
        path: Path to image or PDF file
        
    Returns:
        Image as numpy array (first page if PDF)
        
    Note: For PDFs with multiple pages, use load_all_pages() instead
    """
    path = str(path)
    if path.lower().endswith(".pdf"):
        pages = convert_from_path(path, dpi=300)
        if not pages:
            raise ValueError(f"PDF has no pages: {path}")
        img = np.array(pages[0])
    else:
        img = cv2.imread(path)
        if img is None:
            raise ValueError(f"Could not load image from {path}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return img

def load_all_pages(path: Path) -> List[np.ndarray]:
    """
    Load all pages from PDF or single image
    
    Args:
        path: Path to image or PDF file
        
    Returns:
        List of images as numpy arrays (one per page)
    """
    path_str = str(path)
    if path_str.lower().endswith(".pdf"):
        try:
            pages = convert_from_path(path_str, dpi=300)
            if not pages:
                raise ValueError(f"PDF has no pages: {path_str}")
            
            images = []
            for page in pages:
                img = np.array(page)
                images.append(img)
            return images
        except Exception as e:
            # Fallback to PyMuPDF if pdf2image fails
            try:
                import fitz
                doc = fitz.open(path_str)
                images = []
                zoom = 300 / 72.0  # DPI conversion
                mat = fitz.Matrix(zoom, zoom)
                
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    pix = page.get_pixmap(matrix=mat)
                    # Convert pixmap to numpy array
                    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                        (pix.height, pix.width, pix.n)
                    )
                    if pix.n == 4:  # RGBA
                        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
                    elif pix.n == 1:  # Grayscale
                        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
                    images.append(img)
                
                doc.close()
                return images
            except ImportError:
                raise ValueError(f"PDF conversion failed: {e}. Install poppler-utils or PyMuPDF")
            except Exception as fallback_error:
                raise ValueError(f"PDF conversion failed: {e}. PyMuPDF fallback also failed: {fallback_error}")
    else:
        # Single image file
        img = cv2.imread(path_str)
        if img is None:
            raise ValueError(f"Could not load image from {path_str}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return [img]

def run_ocr(image: np.ndarray):
    """
    Run OCR on image
    
    Args:
        image: Image as numpy array
        
    Returns:
        Tuple of (texts, boxes)
    """
    import time
    
    start_time = time.time()
    print("      Calling OCR predict...")
    
    try:
        ocr = get_ocr()
        
        if ocr is None:
            raise RuntimeError("OCR instance is not initialized")
        
        print("      OCR instance ready, running prediction...")
        results = ocr.predict(image)
        
        elapsed = time.time() - start_time
        print(f"      ✓ OCR prediction completed in {elapsed:.1f}s")
        
        if not results:
            return [], []

        res = results[0]
        texts = res.json['res'].get('rec_texts', [])
        polys = res.json['res'].get('dt_polys', [])

        boxes = []
        for poly in polys:
            poly = np.array(poly, dtype=np.float32)
            xs = poly[:, 0]
            ys = poly[:, 1]
            boxes.append([int(np.min(xs)), int(np.min(ys)), int(np.max(xs)), int(np.max(ys))])

        return texts, boxes
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"      ❌ OCR failed after {elapsed:.1f}s: {str(e)[:150]}")
        raise

def group_lines(words, boxes, y_thresh=25, x_gap_thresh=80):
    lines = []

    for word, box in zip(words, boxes):
        y_center = (box[1] + box[3]) // 2
        placed = False
        for line in lines:
            if abs(line["y"] - y_center) < y_thresh:
                if max(b[2] for b in line["boxes"]) + x_gap_thresh < box[0]:
                    continue
                line["words"].append(word)
                line["boxes"].append(box)
                placed = True
                break
        if not placed:
            lines.append({"y": y_center, "words": [word], "boxes": [box]})

    lines.sort(key=lambda l: l["y"])
    for line in lines:
        paired = sorted(zip(line["words"], line["boxes"]), key=lambda p: p[1][0])
        line["words"], line["boxes"] = [p[0] for p in paired], [p[1] for p in paired]
        line["text"] = " ".join(line["words"])
        line["bbox"] = [
            min(b[0] for b in line["boxes"]),
            min(b[1] for b in line["boxes"]),
            max(b[2] for b in line["boxes"]),
            max(b[3] for b in line["boxes"]),
        ]
    return lines

def extract_english_text(file_path: Path) -> str:
    """
    High-level OCR extraction function.
    Processes all pages if PDF, returns concatenated text from all pages.
    
    Args:
        file_path: Path to image or PDF file
        
    Returns:
        Concatenated text from all pages
    """
    # Load all pages (handles both PDFs and images)
    images = load_all_pages(file_path)
    
    if not images:
        return ""
    
    all_text_lines = []
    
    for page_num, img in enumerate(images, 1):
        if len(images) > 1:
            print(f"      Processing page {page_num}/{len(images)}...")
        
        try:
            words, boxes = run_ocr(img)
            
            if not words:
                if len(images) > 1:
                    print(f"      ⚠️ Page {page_num}: No text found")
                continue
            
            lines = group_lines(words, boxes)
            page_text = "\n".join([l["text"] for l in lines])
            
            if len(images) > 1:
                # Add page separator for multi-page documents
                all_text_lines.append(f"[Page {page_num}]\n{page_text}")
                print(f"      ✓ Page {page_num}: {len(page_text)} characters")
            else:
                all_text_lines.append(page_text)
                
        except Exception as e:
            error_msg = str(e)[:100]
            if len(images) > 1:
                print(f"      ❌ Page {page_num} OCR failed: {error_msg}")
                # Continue with other pages
            else:
                raise
    
    # Combine all pages
    result = "\n\n".join(all_text_lines)
    
    if len(images) > 1:
        print(f"      ✓ Total: {len(result)} characters from {len(images)} pages")
    
    return result