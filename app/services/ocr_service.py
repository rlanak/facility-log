import re
import shutil
from functools import lru_cache
from pathlib import Path

import pytesseract
from PIL import Image, ImageOps


_DIGITS_RE = re.compile(r"[0-9.,]+")

# The UB-Mannheim Windows installer (winget install UB-Mannheim.TesseractOCR)
# doesn't reliably put tesseract.exe on PATH, so `shutil.which` alone often
# misses a real install — check its default locations too before giving up.
_COMMON_WINDOWS_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def _locate_tesseract() -> str | None:
    found = shutil.which("tesseract")
    if found:
        return found
    for path in _COMMON_WINDOWS_PATHS:
        if Path(path).is_file():
            return path
    return None


@lru_cache(maxsize=1)
def is_available() -> bool:
    found = _locate_tesseract()
    if found:
        pytesseract.pytesseract.tesseract_cmd = found
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

    # NEAREST, not LANCZOS: real Foxhole stockpile counts are only ~10-15px
    # tall at native screenshot resolution, rendered in a thin stylized font.
    # LANCZOS's smoothing blurs those already-thin anti-aliased strokes into
    # mush at this size; NEAREST keeps hard pixel edges Tesseract can actually
    # segment. Verified against real game screenshots (not just the synthetic
    # test) — this measurably fixed cases LANCZOS got wrong, though neither
    # is anywhere near 100% reliable at this source resolution, especially
    # once any icon pixels bleed into the crop (see ocr_coverage memory note).
    crop = crop.resize((crop.width * 6, crop.height * 6), Image.NEAREST)
    crop = ImageOps.grayscale(crop)
    crop = ImageOps.autocontrast(crop)
    return crop


def read_crop(image_path: Path, box: tuple[int, int, int, int], psm: int = 7) -> dict:
    if not is_available():
        return {"available": False, "raw_text": "", "guess": ""}

    crop = _prepare_crop(image_path, box)
    raw_text = pytesseract.image_to_string(
        crop, config=f"--psm {psm} -c tessedit_char_whitelist=0123456789.,kKmM"
    ).strip()

    digits_only = "".join(_DIGITS_RE.findall(raw_text))
    if not any(c.isdigit() for c in digits_only):
        # Tesseract can return pure punctuation (a stray "." or ",") on a
        # noisy crop -- _DIGITS_RE matches that as a non-empty "guess" even
        # though it has no actual digit, which crashes quantity parsing
        # downstream instead of just failing to read. Treat it as no guess.
        digits_only = ""
    return {"available": True, "raw_text": raw_text, "guess": digits_only}
