# import os
# import shutil
# import uuid

# from anyio import Path
# import fitz  # pymupdf
# from PIL import Image

# UPLOAD_DIR = "uploads"
# os.makedirs(UPLOAD_DIR, exist_ok=True)

# def save_upload_file(upload_file) -> str:
#     ext = upload_file.filename.split(".")[-1]
#     filename = f"{uuid.uuid4()}.{ext}"
#     path = os.path.join(UPLOAD_DIR, filename)

#     with open(path, "wb") as f:
#         f.write(upload_file.file.read())

#     return path


# def pdf_to_images(pdf_path: str) -> list[str]:
#     images = []
#     doc = fitz.open(pdf_path)

#     for page_index in range(len(doc)):
#         page = doc[page_index]
#         pix = page.get_pixmap()
#         image_path = pdf_path.replace(".pdf", f"_page{page_index}.png")
#         pix.save(image_path)
#         images.append(image_path)

#     return images


# def prepare_files(file_paths: list[str]) -> list[str]:
#     image_paths = []

#     for path in file_paths:
#         if path.lower().endswith(".pdf"):
#             image_paths.extend(pdf_to_images(path))
#         else:
#             image_paths.append(path)

#     return image_paths

import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional, Union
from enum import Enum

import fitz  # pymupdf
from fastapi import UploadFile


# Configuration
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class UploadType(str, Enum):
    """Enum for upload types"""
    FORMS = "forms"
    DOCS = "docs"


class FileConfig:
    """Configuration for file processing"""
    def __init__(
        self,
        use_uuid: bool = True,
        convert_pdf: bool = True,
        delete_original_pdf: bool = True,
        zoom_factor: float = 2.0,  # 2.0 = ~144 DPI, 4.17 = 300 DPI
        image_format: str = "png"
    ):
        self.use_uuid = use_uuid
        self.convert_pdf = convert_pdf
        self.delete_original_pdf = delete_original_pdf
        self.zoom_factor = zoom_factor
        self.image_format = image_format


def ensure_folder(
    user_id: Optional[str] = None,
    upload_type: Optional[str] = None,
    custom_path: Optional[str] = None
) -> Path:
    """
    Create folder structure flexibly
    
    Args:
        user_id: User identifier (creates user folder)
        upload_type: 'forms' or 'docs' (creates subfolder)
        custom_path: Custom path relative to UPLOAD_DIR
    
    Returns:
        Path object of created folder
    
    Examples:
        ensure_folder() -> uploads/
        ensure_folder("user123") -> uploads/user123/
        ensure_folder("user123", "forms") -> uploads/user123/forms/
        ensure_folder(custom_path="temp/processing") -> uploads/temp/processing/
    """
    if custom_path:
        folder_path = Path(UPLOAD_DIR) / custom_path
    else:
        parts = [UPLOAD_DIR]
        if user_id:
            parts.append(user_id)
        if upload_type:
            parts.append(upload_type)
        folder_path = Path(*parts)
    
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path


async def save_upload(
    file: UploadFile,
    destination: Union[str, Path],
    use_uuid: bool = True,
    keep_original_name: bool = False
) -> str:
    """
    Save uploaded file with flexible naming options
    
    Args:
        file: FastAPI UploadFile object
        destination: Folder path to save file
        use_uuid: Generate UUID filename (default: True)
        keep_original_name: Keep original filename (overrides use_uuid)
    
    Returns:
        Full path to saved file
    """
    destination = Path(destination)
    
    if keep_original_name:
        filename = file.filename
    elif use_uuid:
        ext = Path(file.filename).suffix
        filename = f"{uuid.uuid4()}{ext}"
    else:
        filename = file.filename
    
    file_path = destination / filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        await file.close()
    
    return str(file_path)


def convert_pdf_to_images(
    pdf_path: Union[str, Path],
    output_folder: Optional[Union[str, Path]] = None,
    zoom_factor: float = 4.17,  # 300 DPI
    image_format: str = "png",
    delete_pdf: bool = True,
    filename_pattern: Optional[str] = None
) -> List[str]:
    """
    Convert PDF to images with flexible options
    
    Args:
        pdf_path: Path to PDF file
        output_folder: Where to save images (default: same as PDF)
        zoom_factor: Resolution (2.0=144dpi, 4.17=300dpi)
        image_format: 'png' or 'jpg'
        delete_pdf: Delete original PDF after conversion
        filename_pattern: Custom pattern like "{base}_page_{num}" or None for default
    
    Returns:
        List of image paths
    """
    pdf_path = Path(pdf_path)
    output_folder = Path(output_folder) if output_folder else pdf_path.parent
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    images = []
    
    try:
        doc = fitz.open(str(pdf_path))
        mat = fitz.Matrix(zoom_factor, zoom_factor)
        base_name = pdf_path.stem
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)
            
            # Generate filename
            if filename_pattern:
                image_name = filename_pattern.format(
                    base=base_name, 
                    num=page_num + 1
                ) + f".{image_format}"
            else:
                image_name = f"{base_name}_page_{page_num + 1}.{image_format}"
            
            image_path = output_folder / image_name
            pix.save(str(image_path))
            images.append(str(image_path))
        
        doc.close()
        
        # Delete original PDF if requested
        if delete_pdf and images:
            pdf_path.unlink()
    
    except Exception as e:
        raise Exception(f"PDF conversion failed: {str(e)}")
    
    return images


async def process_upload(
    file: UploadFile,
    user_id: str,
    upload_type: str,
    config: Optional[FileConfig] = None
) -> dict:
    """
    Complete upload processing pipeline
    
    Args:
        file: FastAPI UploadFile object
        user_id: User identifier
        upload_type: 'forms' or 'docs'
        config: FileConfig object for custom processing
    
    Returns:
        Dict with processing results
    """
    if config is None:
        config = FileConfig()
    
    # Create user folder
    folder = ensure_folder(user_id, upload_type)
    
    # Save file
    file_path = await save_upload(
        file, 
        folder, 
        use_uuid=config.use_uuid
    )
    
    result = {
        "user_id": user_id,
        "upload_type": upload_type,
        "original_filename": file.filename,
        "saved_path": file_path,
        "files": [file_path],
        "is_converted": False
    }
    
    # Check if PDF conversion needed
    if config.convert_pdf and file_path.lower().endswith('.pdf'):
        try:
            image_paths = convert_pdf_to_images(
                file_path,
                output_folder=folder,
                zoom_factor=config.zoom_factor,
                image_format=config.image_format,
                delete_pdf=config.delete_original_pdf
            )
            result["files"] = image_paths
            result["is_converted"] = True
            result["total_pages"] = len(image_paths)
        except Exception as e:
            result["error"] = str(e)
    
    return result


def batch_convert_pdfs(
    file_paths: List[str],
    config: Optional[FileConfig] = None
) -> List[str]:
    """
    Convert multiple PDFs or return images as-is
    
    Args:
        file_paths: List of file paths
        config: FileConfig for conversion settings
    
    Returns:
        List of all image paths (PDFs converted, images unchanged)
    """
    if config is None:
        config = FileConfig()
    
    all_images = []
    
    for path in file_paths:
        path_obj = Path(path)
        
        if path_obj.suffix.lower() == '.pdf' and config.convert_pdf:
            images = convert_pdf_to_images(
                path,
                zoom_factor=config.zoom_factor,
                image_format=config.image_format,
                delete_pdf=config.delete_original_pdf
            )
            all_images.extend(images)
        else:
            all_images.append(path)
    
    return all_images


def get_files(
    user_id: Optional[str] = None,
    upload_type: Optional[str] = None,
    extension: Optional[str] = None,
    custom_path: Optional[str] = None
) -> List[str]:
    """
    Retrieve files with flexible filtering
    
    Args:
        user_id: Filter by user
        upload_type: Filter by type ('forms' or 'docs')
        extension: Filter by extension (e.g., '.png', '.pdf')
        custom_path: Search in custom path
    
    Returns:
        List of file paths
    
    Examples:
        get_files("user123") -> all files for user123
        get_files("user123", "forms") -> only forms
        get_files("user123", "forms", ".png") -> only PNG forms
        get_files(custom_path="temp") -> files in temp folder
    """
    if custom_path:
        search_path = Path(UPLOAD_DIR) / custom_path
    else:
        search_path = ensure_folder(user_id, upload_type)
    
    if not search_path.exists():
        return []
    
    # Collect files
    files = []
    
    if upload_type:
        # Single folder
        files = [str(f) for f in search_path.iterdir() if f.is_file()]
    else:
        # Search recursively
        files = [str(f) for f in search_path.rglob('*') if f.is_file()]
    
    # Filter by extension if provided
    if extension:
        extension = extension if extension.startswith('.') else f'.{extension}'
        files = [f for f in files if Path(f).suffix.lower() == extension]
    
    return files


def delete_files(
    user_id: Optional[str] = None,
    upload_type: Optional[str] = None,
    file_path: Optional[str] = None,
    custom_path: Optional[str] = None
) -> bool:
    """
    Delete files/folders flexibly
    
    Args:
        user_id: Delete user folder
        upload_type: Delete specific type folder
        file_path: Delete specific file
        custom_path: Delete custom path
    
    Returns:
        True if successful
    
    Examples:
        delete_files(user_id="user123") -> delete all user files
        delete_files(user_id="user123", upload_type="forms") -> delete only forms
        delete_files(file_path="/path/to/file.png") -> delete specific file
    """
    try:
        if file_path:
            # Delete specific file
            Path(file_path).unlink(missing_ok=True)
        elif custom_path:
            # Delete custom path
            path = Path(UPLOAD_DIR) / custom_path
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        else:
            # Delete user/type folder
            folder = ensure_folder(user_id, upload_type)
            if folder.exists():
                shutil.rmtree(folder)
        
        return True
    except Exception as e:
        print(f"Delete error: {str(e)}")
        return False


def get_file_info(file_path: Union[str, Path]) -> dict:
    """
    Get file information
    
    Args:
        file_path: Path to file
    
    Returns:
        Dict with file details
    """
    path = Path(file_path)
    
    if not path.exists():
        return {"error": "File not found"}
    
    return {
        "filename": path.name,
        "extension": path.suffix,
        "size_bytes": path.stat().st_size,
        "size_mb": round(path.stat().st_size / (1024 * 1024), 2),
        "full_path": str(path.absolute()),
        "exists": True
    }