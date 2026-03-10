"""
Form PDF Overlay Service

Fills the original form PDF by overlaying text and checkmarks on form fields.
- Coordinates from extraction come from Docling, which runs on *rendered images*
  (e.g. PDF rendered at 300 DPI). Docling uses BOTTOMLEFT origin (y-axis up).
  We convert to top-left (y down) then scale to PDF points: pdf_coord = image_coord * (72 / render_dpi).
- When the form was uploaded as an image (not PDF), no scaling is needed (render_dpi=None).
- Supports: text_input, textarea, date, checkbox, dropdown; signature/image_upload.
"""

import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    fitz = None

from PIL import Image


# Value text goes in the fill area *in front of* (immediately after) the field name
VALUE_BOX_GAP = 5
VALUE_BOX_WIDTH = 200
VALUE_BOX_HEIGHT_EXTRA = 2
# Nudge value box down so text sits on the fill line (below label), not floating above
VALUE_BOX_TOP_NUDGE = 4
# Max chars for textarea to avoid overflow into next field
TEXTAREA_MAX_CHARS = 80
DEFAULT_FONT_SIZE = 9
FONT_NAME = "helv"  # Helvetica, good for forms

# Radio-style fields: one bbox spans multiple options; we draw check in left or right half
RADIO_OPTIONS = {
    "gender": ("Male", "Female"),   # order on form: Male then Female
    "status": ("Single", "Married"),
}


def _normalize_label_rect(
    c0: float, c1: float, c2: float, c3: float,
) -> Tuple[float, float, float, float]:
    """Normalize [left, top, right, bottom] so left < right, top < bottom (top-left coords)."""
    left = min(c0, c2)
    right = max(c0, c2)
    top = min(c1, c3)
    bottom = max(c1, c3)
    return (left, top, right, bottom)


def _docling_bbox_to_topleft(
    left: float, top_bl: float, right: float, bottom_bl: float,
    page_height_px: float,
) -> Tuple[float, float, float, float]:
    """
    Convert Docling BOTTOMLEFT bbox [l, t, r, b] (y-axis up) to top-left [l, top, r, bottom] (y down).
    Docling: (l, b) = left-bottom, (r, t) = right-top; larger y = higher on page.
    Top-left: (left, top) = top-left, (right, bottom) = bottom-right; larger y = lower on page.
    So: top_tl = page_height_px - top_bl, bottom_tl = page_height_px - bottom_bl.
    """
    top_tl = page_height_px - top_bl
    bottom_tl = page_height_px - bottom_bl
    return (left, top_tl, right, bottom_tl)


def _label_bbox_to_value_bbox(
    left: float, top: float, right: float, bottom: float,
    gap: float = VALUE_BOX_GAP,
    width: float = VALUE_BOX_WIDTH,
    height_extra: float = VALUE_BOX_HEIGHT_EXTRA,
    page_width: Optional[float] = None,
    nudge_down: float = VALUE_BOX_TOP_NUDGE,
) -> Tuple[float, float, float, float]:
    """Value box is the fill area in front of the field name; nudge down so text sits on the line."""
    value_left = right + gap
    value_right = value_left + width
    # Nudge down so value sits on the fill line, not floating above
    value_top = top + nudge_down
    value_bottom = bottom + height_extra + nudge_down
    if page_width is not None and value_right > page_width - 5:
        value_right = page_width - 5
    return (value_left, value_top, value_right, value_bottom)


def _make_finite_rect(x0: float, y0: float, x1: float, y1: float, min_w: float = 10, min_h: float = 8) -> "fitz.Rect":
    """Ensure rect is finite and has positive width/height."""
    left = min(x0, x1)
    right = max(x0, x1)
    top = min(y0, y1)
    bottom = max(y0, y1)
    if right - left < min_w:
        right = left + min_w
    if bottom - top < min_h:
        bottom = top + min_h
    return fitz.Rect(left, top, right, bottom)


def _is_checkbox_checked(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    return s in ("true", "yes", "1", "checked", "x", "✓", "✔")


def _get_radio_option_index(field_key: str, value: Any) -> Optional[int]:
    """For radio-style fields (Gender, Status), return 0 = first option, 1 = second, or None."""
    if value is None or field_key not in RADIO_OPTIONS:
        return None
    options = RADIO_OPTIONS[field_key]
    s = str(value).strip()
    for i, opt in enumerate(options):
        if s.lower() == opt.lower():
            return i
    return None


def _radio_rect_for_option(rect: "fitz.Rect", option_index: int, num_options: int = 2) -> "fitz.Rect":
    """Split rect into horizontal slots; return the rect for the given option (0-based)."""
    x0, y0, x1, y1 = rect.x0, rect.y0, rect.x1, rect.y1
    w = x1 - x0
    slot_w = w / num_options
    left = x0 + option_index * slot_w
    right = left + slot_w
    return fitz.Rect(left, y0, right, y1)


def _draw_checkmark(page: "fitz.Page", rect: "fitz.Rect") -> None:
    """Draw a checkmark inside the given rectangle (X or ✓)."""
    x0, y0, x1, y1 = rect.x0, rect.y0, rect.x1, rect.y1
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    h = y1 - y0
    fontsize = max(6, min(h * 0.8, 12))
    # insert_text uses baseline; offset so character is roughly centered
    try:
        page.insert_text(
            fitz.Point(cx - fontsize * 0.3, cy + fontsize * 0.35),
            "✓",
            fontsize=fontsize,
            fontname=FONT_NAME,
            color=(0, 0, 0),
        )
    except Exception:
        page.insert_text(
            fitz.Point(cx - fontsize * 0.25, cy + fontsize * 0.35),
            "X",
            fontsize=fontsize,
            fontname=FONT_NAME,
            color=(0, 0, 0),
        )


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


class FormPdfOverlayService:
    """
    Overlays filled values onto the original form PDF.
    Uses label bboxes to place value text to the right; checkboxes get a checkmark.
    """

    def __init__(self):
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDF (fitz) is required. Install with: pip install pymupdf")

    def fill_pdf(
        self,
        original_path: Path,
        filled_fields: List[Dict[str, Any]],
        page_image_paths: Optional[List[str]] = None,
        output_path: Optional[Path] = None,
        render_dpi: Optional[int] = None,
    ) -> Path:
        """
        Create a filled PDF by overlaying text and checkmarks on the form.

        Coordinate scaling:
        - When the form was a PDF, it is rendered at render_dpi (e.g. 300) for Docling.
          Docling bboxes are in image-pixel space. The overlay draws on the original PDF
          in points (72 per inch). Scale: pdf_coord = image_coord * (72 / render_dpi).
        - When the form was an image (PNG/JPEG), render_dpi should be None; then no
          scaling is applied (page size = image size, coords already in pixel space).

        Args:
            original_path: Path to the original form (PDF or image). If image, converted to 1-page PDF.
            filled_fields: List of field dicts with field_key, field_type, value, coordinates, page_number.
            page_image_paths: Unused (kept for API compatibility).
            output_path: Where to save the filled PDF. If None, saves next to original with _filled suffix.
            render_dpi: DPI at which the form was rendered for Docling (e.g. 300). None if form was an image.

        Returns:
            Path to the saved filled PDF.
        """
        original_path = Path(original_path)
        if not original_path.exists():
            raise FileNotFoundError(f"Form file not found: {original_path}")

        # Image-space → PDF points: scale = 72 / render_dpi. If no render_dpi (image upload), scale = 1.
        scale = (72.0 / render_dpi) if render_dpi else 1.0

        suffix = original_path.suffix.lower()
        if suffix == ".pdf":
            doc = fitz.open(str(original_path))
        else:
            # Single image form: create one-page PDF with image as background.
            # MuPDF rejects some PNG/JPEG variants; re-encode with PIL to standard PNG.
            doc = fitz.open()
            with Image.open(original_path) as img:
                w, h = img.size
                img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                img_bytes = buf.getvalue()
            # Page size in points (1:1 with pixels so overlay coords match; scale stays 1)
            page = doc.new_page(width=float(w), height=float(h))
            page.insert_image(page.rect, stream=img_bytes)

        # Sort by position (page, top, left) so we draw in form reading order and mapping stays correct
        def _field_position_key(f: Dict[str, Any]) -> tuple:
            c = f.get("coordinates") or [0, 0, 0, 0]
            if len(c) < 4:
                return (f.get("page_number", 1), 0.0, 0.0)
            # In Docling BOTTOMLEFT, smaller y = lower on page; use min for stable sort
            return (f.get("page_number", 1), min(c[1], c[3]), min(c[0], c[2]))

        filled_fields = sorted(filled_fields, key=_field_position_key)

        for field in filled_fields:
            value = field.get("value")
            field_type = (field.get("field_type") or "text_input").strip().lower()
            page_no = field.get("page_number", 1)
            coords = field.get("coordinates")
            if not coords or len(coords) < 4:
                continue

            page_index = max(0, int(page_no) - 1)
            if page_index >= len(doc):
                continue

            page = doc[page_index]
            pdf_rect = page.rect
            # Page height in the same units as extraction coords (image pixels when render_dpi, else points)
            page_height_same_units = pdf_rect.height * (render_dpi / 72.0) if render_dpi else pdf_rect.height
            # Extraction coords are from Docling: [left, top_bl, right, bottom_bl] in BOTTOMLEFT (y up)
            c0, c1, c2, c3 = float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3])
            left, top, right, bottom = _docling_bbox_to_topleft(
                c0, c1, c2, c3, page_height_same_units
            )
            left, top, right, bottom = _normalize_label_rect(left, top, right, bottom)
            # Scale to PDF points
            left = left * scale
            top = top * scale
            right = right * scale
            bottom = bottom * scale
            label_rect = _make_finite_rect(left, top, right, bottom, min_w=4, min_h=4)

            # Checkbox and radio: draw checkmark (for radio, in the correct option half)
            if field_type in ("checkbox", "radio"):
                field_key = (field.get("field_key") or "").strip().lower()
                radio_idx = _get_radio_option_index(field_key, value)
                if radio_idx is not None:
                    # Radio-style: draw check in left or right half of bbox
                    option_rect = _radio_rect_for_option(label_rect, radio_idx)
                    _draw_checkmark(page, option_rect)
                elif _is_checkbox_checked(value):
                    _draw_checkmark(page, label_rect)
                continue

            # Value goes in the fill area in front of the field name (nudged down onto the line)
            value_left, value_top, value_right, value_bottom = _label_bbox_to_value_bbox(
                left, top, right, bottom,
                page_width=pdf_rect.width,
            )
            value_rect = _make_finite_rect(
                value_left, value_top, value_right, value_bottom,
                min_w=VALUE_BOX_WIDTH, min_h=14,
            )
            text = _safe_text(value)
            if not text:
                continue

            # Truncate long text (especially textarea) to avoid overlapping next field
            if field_type == "textarea" and len(text) > TEXTAREA_MAX_CHARS:
                text = text[: TEXTAREA_MAX_CHARS - 3].rstrip() + "..."
            elif len(text) > 60:
                text = text[:57] + "..."

            if field_type in ("signature", "image_upload"):
                text = f"[{text}]" if len(text) < 30 else text[:27] + "..."

            fontsize = DEFAULT_FONT_SIZE
            rc = page.insert_textbox(
                value_rect,
                text,
                fontsize=fontsize,
                fontname=FONT_NAME,
                align=0,
            )
            if rc < 0:
                # Text didn't fit; try smaller font and truncate
                short = text[:50] + ("..." if len(text) > 50 else "")
                page.insert_textbox(
                    value_rect,
                    short,
                    fontsize=max(6, fontsize - 2),
                    fontname=FONT_NAME,
                    align=0,
                )

        if output_path is None:
            output_path = original_path.parent / f"{original_path.stem}_filled.pdf"
        output_path = Path(output_path)
        doc.save(str(output_path), garbage=4, deflate=True)
        doc.close()
        return output_path


form_pdf_overlay_service = FormPdfOverlayService()
