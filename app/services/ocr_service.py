import re
from functools import lru_cache
from pathlib import Path

import pytesseract
from PIL import Image, ImageOps

_DIGITS_RE = re.compile(r"[0-9.,]+")


@lru_cache(maxsize=1)
def is_available() -> bool:
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _prepare_crop(image_path: Path, box: tuple[int, int, int, int]) -> Image.Image:
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        width, height = img.size
        x0, y0, x1, y1 = box
        x0 = max(0, min(x0, width))
        y0 = max(0, min(y0, height))
        x1 = max(x0 + 1, min(x1, width))
        y1 = max(y0 + 1, min(y1, height))
        crop = img.crop((x0, y0, x1, y1))

    crop = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
    crop = ImageOps.grayscale(crop)
    crop = ImageOps.autocontrast(crop)
    return crop


def read_crop(image_path: Path, box: tuple[int, int, int, int]) -> dict:
    if not is_available():
        return {"available": False, "raw_text": "", "guess": ""}

    crop = _prepare_crop(image_path, box)
    raw_text = pytesseract.image_to_string(
        crop, config="--psm 7 -c tessedit_char_whitelist=0123456789.,kKmM"
    ).strip()

    digits_only = "".join(_DIGITS_RE.findall(raw_text))
    return {"available": True, "raw_text": raw_text, "guess": digits_only}
