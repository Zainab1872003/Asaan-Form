# app/services/ocr_service.py

from typing import Union
from pathlib import Path

_ocr_instance = None

def get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
    
        from paddleocr import PaddleOCR
        _ocr_instance = PaddleOCR(
            use_angle_cls=True,
            lang="en",
            show_log=False
        )
    return _ocr_instance


def extract_text_from_image(file_path: Union[str, Path]) -> str:
    ocr = get_ocr()
    result = ocr.ocr(str(file_path), cls=True)

    lines = []
    for page in result:
        for line in page:
            lines.append(line[1][0])

    return "\n".join(lines)
