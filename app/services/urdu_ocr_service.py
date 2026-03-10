import torch
from PIL import Image

from models.utrnet.model import Model
from models.utrnet.read import text_recognizer
from models.utrnet.utils import CTCLabelConverter


# --------------------------------------------------
# Global lazy-loaded objects
# --------------------------------------------------
_device = None
_converter = None
_recognition_model = None
_detection_model = None


# --------------------------------------------------
# Load everything ONCE
# --------------------------------------------------
def _load_models():
    global _device, _converter, _recognition_model, _detection_model

    if _recognition_model is not None:
        return  # already loaded

    # Lazy import so app startup does not require ultralytics/pkg_resources (avoids spawn issues)
    from ultralytics import YOLO
    from ultralytics.nn.tasks import DetectionModel
    if hasattr(torch.serialization, "add_safe_globals"):
        torch.serialization.add_safe_globals([DetectionModel])

    print("Loading UTRNet models...")

    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # ---- Load Urdu vocabulary ----
    with open(
        "models/utrnet/UrduGlyphs.txt",
        "r",
        encoding="utf-8"
    ) as f:
        chars = f.read().replace("\n", "") + " "

    _converter = CTCLabelConverter(chars)

    # ---- Load recognition model ----
    _recognition_model = Model(
        num_class=len(_converter.character),
        device=_device
    ).to(_device)

    _recognition_model.load_state_dict(
        torch.load(
            "models/utrnet/best_norm_ED.pth",
            map_location=_device
        )
    )

    _recognition_model.eval()

    # ---- Load detection model ----
    _detection_model = YOLO(
        "models/utrnet/yolov8m_UrduDoc.pt"
    )

    print("UTRNet loaded successfully")

def extract_urdu_text(file_path: str) -> str:
    """
    Urdu OCR service using UTRNet.
    Called by urdu_ocr_agent.
    """
    _load_models()

    image = Image.open(file_path).convert("RGB")

    # ---- Line detection ----
    results = _detection_model.predict(
        source=image,
        conf=0.2,
        imgsz=1280,
        save=False,
        nms=True,
        device=0 if _device.type == "cuda" else "cpu"
    )

    if not results or results[0].boxes is None:
        return ""

    boxes = results[0].boxes.xyxy.cpu().numpy().tolist()

    # Sort top-to-bottom (Urdu reading order)
    boxes.sort(key=lambda b: b[1])

    # ---- Text recognition ----
    lines = []
    for box in boxes:
        crop = image.crop(box)
        text = text_recognizer(
            crop,
            _recognition_model,
            _converter,
            _device
        )
        if text.strip():
            lines.append(text)

    return "\n".join(lines)