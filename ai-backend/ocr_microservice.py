# import torch
# import gc
# from fastapi import FastAPI
# from pydantic import BaseModel
# import cv2
# import numpy as np
# from PIL import Image
# from pathlib import Path
# from typing import List

# # UTRNet dependencies
# from ultralytics import YOLO
# from ultralytics.nn.tasks import DetectionModel
# from app.models.utrnet.model import Model
# from app.models.utrnet.read import text_recognizer
# from app.models.utrnet.utils import CTCLabelConverter

# try:
#     from pdf2image import convert_from_path
# except ImportError:
#     convert_from_path = None

# import fitz
# from paddleocr import PaddleOCR

# app = FastAPI(title="OCR Microservice")

# class OCRRequest(BaseModel):
#     file_path: str

# # --------------------------------------------------
# # 1. Initialize Models Once at Startup
# # --------------------------------------------------
# _use_gpu = torch.cuda.is_available()
# print(f"Initializing PaddleOCR (GPU={_use_gpu})...")
# # Standard English engine
# # ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=_use_gpu, show_log=False)
# ocr_engine = PaddleOCR(use_angle_cls=True, lang='en')
# print("PaddleOCR Initialized.")

# if hasattr(torch.serialization, "add_safe_globals"):
#     torch.serialization.add_safe_globals([DetectionModel])

# print("Loading UTRNet models...")
# _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# with open("app/models/utrnet/UrduGlyphs.txt", "r", encoding="utf-8") as f:
#     chars = f.read().replace("\n", "") + " "
# _converter = CTCLabelConverter(chars)

# _recognition_model = Model(num_class=len(_converter.character), device=_device).to(_device)
# _recognition_model.load_state_dict(torch.load("app/models/utrnet/best_norm_ED.pth", map_location=_device))
# _recognition_model.eval()

# _detection_model = YOLO("app/models/utrnet/yolov8m_UrduDoc.pt")
# print("UTRNet loaded successfully")

# # --------------------------------------------------
# # 2. English OCR Helper Functions
# # --------------------------------------------------
# def load_all_pages(path_str: str) -> List[np.ndarray]:
#     if path_str.lower().endswith(".pdf"):
#         try:
#             if convert_from_path:
#                 pages = convert_from_path(path_str, dpi=300)
#                 if pages:
#                     return [np.array(p) for p in pages]
#         except Exception:
#             pass
            
#         doc = fitz.open(path_str)
#         images = []
#         zoom = 300 / 72.0
#         mat = fitz.Matrix(zoom, zoom)
        
#         for page_num in range(len(doc)):
#             page = doc[page_num]
#             pix = page.get_pixmap(matrix=mat)
#             img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
#             if pix.n == 4:
#                 img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
#             elif pix.n == 1:
#                 img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
#             images.append(img)
#         doc.close()
#         if not images:
#             raise ValueError("Could not convert PDF to images.")
#         return images
#     else:
#         img = cv2.imread(path_str)
#         if img is None:
#             raise ValueError(f"Could not load image from {path_str}")
#         img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
#         return [img]

# def group_lines(words, boxes, y_thresh=25, x_gap_thresh=80):
#     lines = []
#     for word, box in zip(words, boxes):
#         y_center = (box[1] + box[3]) // 2
#         placed = False
#         for line in lines:
#             if abs(line["y"] - y_center) < y_thresh:
#                 if max(b[2] for b in line["boxes"]) + x_gap_thresh < box[0]:
#                     continue
#                 line["words"].append(word)
#                 line["boxes"].append(box)
#                 placed = True
#                 break
#         if not placed:
#             lines.append({"y": y_center, "words": [word], "boxes": [box]})

#     lines.sort(key=lambda l: l["y"])
#     for line in lines:
#         paired = sorted(zip(line["words"], line["boxes"]), key=lambda p: p[1][0])
#         line["words"], line["boxes"] = [p[0] for p in paired], [p[1] for p in paired]
#         line["text"] = " ".join(line["words"])
#         line["bbox"] = [
#             min(b[0] for b in line["boxes"]),
#             min(b[1] for b in line["boxes"]),
#             max(b[2] for b in line["boxes"]),
#             max(b[3] for b in line["boxes"]),
#         ]
#     return lines

# # --------------------------------------------------
# # 3. Endpoints
# # --------------------------------------------------
# @app.get("/health")
# def health():
#     return {"status": "ok"}

# @app.post("/ocr/english")
# def extract_english(req: OCRRequest):
#     try:
#         images = load_all_pages(req.file_path)
#         if not images:
#             return {"result": [], "text": ""}
        
#         all_text_lines = []
#         first_page_boxes = []
        
#         for page_num, img in enumerate(images, 1):
#             # PaddleOCR.ocr() is the canonical method.
#             # Returns a list of lists: results[0] is the result for the image.
#             # Each entry: [ [ [x1,y1],[x2,y1],[x2,y2],[x1,y2] ], (text, confidence) ]
#             try:
#                 results = ocr_engine.ocr(img, cls=True)
#             except Exception as ocr_inner_err:
#                 print(f"  ⚠️ OCR Engine failed on page {page_num}: {ocr_inner_err}")
#                 continue

#             if not results or not results[0]:
#                 continue
            
#             res_list = results[0]
#             boxes = []
#             words = []
            
#             for line in res_list:
#                 if len(line) >= 2:
#                     boxes.append(line[0])
#                     words.append(line[1][0])
            
#             # Reformat boxes to flat [xmin, ymin, xmax, ymax]
#             flat_boxes = []
#             for b in boxes:
#                 poly = np.array(b, dtype=np.float32)
#                 # Paddle returns 4 points: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
#                 if poly.ndim == 2 and poly.shape[0] == 4:
#                     xs = poly[:, 0]
#                     ys = poly[:, 1]
#                     flat_boxes.append([int(np.min(xs)), int(np.min(ys)), int(np.max(xs)), int(np.max(ys))])
#                 else:
#                     flat_boxes.append(b)
            
#             lines = group_lines(words, flat_boxes)
#             page_text = "\n".join([l["text"] for l in lines])
            
#             if page_num == 1:
#                 first_page_boxes = flat_boxes
                
#             if len(images) > 1:
#                 all_text_lines.append(f"[Page {page_num}]\n{page_text}")
#             else:
#                 all_text_lines.append(page_text)
            
#             # Memory cleanup for large images/documents
#             del results
#             del img
#             gc.collect()
                
#         return {
#             "result": first_page_boxes,
#             "text": "\n\n".join(all_text_lines)
#         }
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return {"error": str(e), "result": [], "text": ""}

# @app.post("/ocr/urdu")
# def extract_urdu(req: OCRRequest):
#     try:
#         image = Image.open(req.file_path).convert("RGB")
#         results = _detection_model.predict(
#             source=image,
#             conf=0.2,
#             imgsz=1280,
#             save=False,
#             nms=True,
#             device=0 if _device.type == "cuda" else "cpu"
#         )

#         if not results or results[0].boxes is None or len(results[0].boxes) == 0:
#             return {"result": [], "text": ""}

#         boxes = results[0].boxes.xyxy.cpu().numpy().tolist()
#         boxes.sort(key=lambda b: b[1])

#         lines = []
#         for i, box in enumerate(boxes, 1):
#             crop = image.crop(box)
#             text = text_recognizer(crop, _recognition_model, _converter, _device)
#             if text.strip():
#                 lines.append(text)

#         return {
#             "result": boxes,
#             "text": "\n".join(lines)
#         }
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return {"error": str(e), "result": [], "text": ""}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("ocr_microservice:app", host="0.0.0.0", port=8001, workers=1)

"""
OCR Microservice - Fixed for new PaddleOCR API
Runs on port 8001.

THE FIX: Removed cls=True from ocr_engine.ocr() call.
New PaddleOCR doesn't accept cls parameter in ocr() / predict().
"""

import gc
import torch
from fastapi import FastAPI
from pydantic import BaseModel
import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List

from ultralytics import YOLO
from ultralytics.nn.tasks import DetectionModel
from app.models.utrnet.model import Model
from app.models.utrnet.read import text_recognizer
from app.models.utrnet.utils import CTCLabelConverter

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

import fitz
from paddleocr import PaddleOCR

app = FastAPI(title="OCR Microservice")

class OCRRequest(BaseModel):
    file_path: str

# --------------------------------------------------
# Initialize Models Once at Startup
# --------------------------------------------------
_use_gpu = torch.cuda.is_available()
print(f"Initializing PaddleOCR (GPU={_use_gpu})...")

# Try new API first, fall back to old API
try:
    ocr_engine = PaddleOCR(use_textline_orientation=True, lang='en', show_log=False)
    _use_new_api = True
    print("PaddleOCR Initialized (new API: use_textline_orientation).")
except TypeError:
    ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
    _use_new_api = False
    print("PaddleOCR Initialized (old API: use_angle_cls).")

if hasattr(torch.serialization, "add_safe_globals"):
    torch.serialization.add_safe_globals([DetectionModel])

print("Loading UTRNet models...")
_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

with open("app/models/utrnet/UrduGlyphs.txt", "r", encoding="utf-8") as f:
    chars = f.read().replace("\n", "") + " "
_converter = CTCLabelConverter(chars)

_recognition_model = Model(num_class=len(_converter.character), device=_device).to(_device)
_recognition_model.load_state_dict(torch.load("app/models/utrnet/best_norm_ED.pth", map_location=_device))
_recognition_model.eval()

_detection_model = YOLO("app/models/utrnet/yolov8m_UrduDoc.pt")
print("UTRNet loaded successfully")


# --------------------------------------------------
# Helper: load image pages from file
# --------------------------------------------------
def load_all_pages(path_str: str) -> List[np.ndarray]:
    if path_str.lower().endswith(".pdf"):
        try:
            if convert_from_path:
                pages = convert_from_path(path_str, dpi=300)
                if pages:
                    return [np.array(p) for p in pages]
        except Exception:
            pass

        doc = fitz.open(path_str)
        images = []
        zoom = 300 / 72.0
        mat = fitz.Matrix(zoom, zoom)
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                (pix.height, pix.width, pix.n)
            )
            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
            elif pix.n == 1:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            images.append(img)
        doc.close()
        if not images:
            raise ValueError("Could not convert PDF to images.")
        return images
    else:
        img = cv2.imread(path_str)
        if img is None:
            raise ValueError(f"Could not load image from {path_str}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return [img]


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


def run_paddle_ocr(img: np.ndarray):
    """
    Run PaddleOCR on an image.
    Handles both new API (predict) and old API (ocr) transparently.
    NEVER passes cls=True — that parameter was removed in newer versions.
    """
    # Try new predict() API first
    if _use_new_api:
        try:
            results = ocr_engine.predict(img)
            if not results:
                return [], []
            res = results[0]
            if hasattr(res, 'json'):
                data = res.json.get('res', {})
                rec_texts = data.get('rec_texts', [])
                dt_polys  = data.get('dt_polys', [])
                boxes, words = [], []
                for txt, poly in zip(rec_texts, dt_polys):
                    if txt and txt.strip():
                        words.append(txt.strip())
                        poly_arr = np.array(poly, dtype=np.float32)
                        xs, ys = poly_arr[:, 0], poly_arr[:, 1]
                        boxes.append([int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())])
                return words, boxes
        except Exception as e:
            print(f"  predict() failed: {e}, falling back to ocr()")

    # Old API: ocr() WITHOUT cls=True
    # cls=True was removed — passing it causes "unexpected keyword argument 'cls'"
    results = ocr_engine.ocr(img)   # ← NO cls=True here
    if not results or not results[0]:
        return [], []

    words, boxes = [], []
    for line in results[0]:
        if len(line) >= 2:
            box_pts = line[0]
            txt = line[1][0]
            if txt and txt.strip():
                words.append(txt.strip())
                poly = np.array(box_pts, dtype=np.float32)
                if poly.ndim == 2 and poly.shape[0] >= 2:
                    xs, ys = poly[:, 0], poly[:, 1]
                    boxes.append([int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())])
    return words, boxes


# --------------------------------------------------
# Endpoints
# --------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "new_api": _use_new_api}


@app.post("/ocr/english")
def extract_english(req: OCRRequest):
    try:
        images = load_all_pages(req.file_path)
        if not images:
            return {"result": [], "text": ""}

        all_text_lines = []
        first_page_boxes = []

        for page_num, img in enumerate(images, 1):
            try:
                words, flat_boxes = run_paddle_ocr(img)
            except Exception as ocr_err:
                print(f"  ⚠️ OCR failed on page {page_num}: {ocr_err}")
                continue

            if not words:
                continue

            lines = group_lines(words, flat_boxes)
            page_text = "\n".join([l["text"] for l in lines])

            if page_num == 1:
                first_page_boxes = flat_boxes

            if len(images) > 1:
                all_text_lines.append(f"[Page {page_num}]\n{page_text}")
            else:
                all_text_lines.append(page_text)

            del img
            gc.collect()

        return {
            "result": first_page_boxes,
            "text": "\n\n".join(all_text_lines),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "result": [], "text": ""}


@app.post("/ocr/urdu")
def extract_urdu(req: OCRRequest):
    try:
        image = Image.open(req.file_path).convert("RGB")
        results = _detection_model.predict(
            source=image,
            conf=0.2,
            imgsz=1280,
            save=False,
            nms=True,
            device=0 if _device.type == "cuda" else "cpu",
        )

        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return {"result": [], "text": ""}

        boxes = results[0].boxes.xyxy.cpu().numpy().tolist()
        boxes.sort(key=lambda b: b[1])

        lines = []
        for box in boxes:
            crop = image.crop(box)
            text = text_recognizer(crop, _recognition_model, _converter, _device)
            if text.strip():
                lines.append(text)

        return {"result": boxes, "text": "\n".join(lines)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "result": [], "text": ""}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ocr_microservice:app", host="0.0.0.0", port=8001, workers=1)
