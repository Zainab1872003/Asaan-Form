import os
import uuid
import fitz  # pymupdf
from PIL import Image

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def save_upload_file(upload_file) -> str:
    ext = upload_file.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    path = os.path.join(UPLOAD_DIR, filename)

    with open(path, "wb") as f:
        f.write(upload_file.file.read())

    return path


def pdf_to_images(pdf_path: str) -> list[str]:
    images = []
    doc = fitz.open(pdf_path)

    for page_index in range(len(doc)):
        page = doc[page_index]
        pix = page.get_pixmap()
        image_path = pdf_path.replace(".pdf", f"_page{page_index}.png")
        pix.save(image_path)
        images.append(image_path)

    return images


def prepare_files(file_paths: list[str]) -> list[str]:
    image_paths = []

    for path in file_paths:
        if path.lower().endswith(".pdf"):
            image_paths.extend(pdf_to_images(path))
        else:
            image_paths.append(path)

    return image_paths
