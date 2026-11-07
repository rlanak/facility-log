"""Number readers for stockpile quantities — every one takes a screenshot path
and a pixel box around one quantity, and returns
{"available", "raw_text", "guess"}.

Which item a slot holds is always decided by icon template matching
(icon_match_service) — that part is good (~0.85-0.97 confidence). What
varies here is only *reading the number* (the weak spot: dropped decimal
points, "1.4k" -> "14k"). Measured Nov 2026 on 32 real
screenshots / 106 confirmed values (with and without an icon mod — see
CLAUDE.md "Captura"): RapidOCR 91, glm-ocr 97, qwen3.5:9b 98,
qwen3-vl:4b 98 (3x-9x slower than glm-ocr). glm-ocr is the recommended local
model: as accurate in practice, by far the fastest, ~2.7GB of VRAM.

A vision model asked to identify the items itself from the whole panel did
far worse (5/30: it can't tell the stylized icons apart), which is why
the AI only ever sees the number crop, never the whole panel.
"""

import base64
import io
import json
import re
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps

_KEEP_RE = re.compile(r"[0-9.,kKmM]")
# A quantity is digits (with . or ,) and at most a trailing k/M — a stray
# letter before the digits is noise (RapidOCR read "1" as "M1").
_QUANTITY_RE = re.compile(r"\d[\d.,]*[kKmM]?")
# Glyphs OCR engines/vision models commonly swap for digits in this font.
_CONFUSABLES = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1", "T": "1", "S": "5", "B": "8"})

# No concrete example numbers in the prompt: given "like 5.1k", qwen3.5
# answered "5.1k" for empty greyed-out slots (seen on a real screenshot).
VLM_PROMPT = (
    "Transcribe the number written in white in this crop from the game Foxhole, exactly as shown: digits, "
    "an optional decimal point and an optional k suffix. Part of an item icon may be visible; ignore it. "
    "If there are no digits in the image, answer NONE."
)
_QUANTITY_SCHEMA = {"type": "object", "properties": {"quantity": {"type": "string"}}, "required": ["quantity"]}


def sanitize(raw: str) -> dict:
    """Raw engine text -> the read_crop() result shape. Keeps only what a
    quantity can contain, after mapping look-alike letters to digits (a real
    RapidOCR read: "3T.9k" for "31.9k", '"5.1k' for "5.1k")."""
    if "NONE" in (raw or "").upper():  # the vision model's "no digits" answer, not "N0NE" -> 0
        return {"available": True, "raw_text": "", "guess": ""}
    kept = "".join(_KEEP_RE.findall((raw or "").translate(_CONFUSABLES)))
    match = _QUANTITY_RE.search(kept)
    text = match.group(0) if match else ""
    has_digit = bool(text)
    return {"available": True, "raw_text": text if has_digit else (raw or ""), "guess": text if has_digit else ""}


def _prepare_crop(image_path: Path, box: tuple[int, int, int, int]) -> Image.Image:
    """Grayscale, high-contrast, 6x crop for the OCR engine. NEAREST, not
    LANCZOS: stockpile counts are only ~10-15px tall in a thin font, and
    smoothing blurs the strokes into mush at this size."""
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        width, height = img.size
        x0, y0, x1, y1 = box
        x0 = max(0, min(x0, width))
        y0 = max(0, min(y0, height))
        x1 = max(x0 + 1, min(x1, width))
        y1 = max(y0 + 1, min(y1, height))
        crop = img.crop((x0, y0, x1, y1))
    crop = crop.resize((crop.width * 6, crop.height * 6), Image.NEAREST)
    return ImageOps.autocontrast(ImageOps.grayscale(crop))


def _crop_png(image_path: Path, box: tuple[int, int, int, int], scale: int = 4) -> bytes:
    with Image.open(image_path) as img:
        crop = img.convert("RGB").crop(box)
    crop = crop.resize((max(1, crop.width * scale), max(1, crop.height * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    crop.save(buf, "PNG")
    return buf.getvalue()


def _post_json(url: str, body: dict, headers: dict | None = None, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json", **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


# --- RapidOCR (free, local, CPU) ---------------------------------------------


def rapidocr_available() -> bool:
    try:
        import rapidocr  # noqa: F401
    except Exception:
        return False
    return True


@lru_cache(maxsize=1)
def _rapid_engine():
    from rapidocr import RapidOCR

    # Recognition only: the box is already around the number, so text
    # detection/orientation would just cost time.
    return RapidOCR(params={"Global.use_det": False, "Global.use_cls": False})


def read_rapidocr(image_path: Path, box: tuple[int, int, int, int]) -> dict:
    import numpy as np

    crop = _prepare_crop(image_path, box)
    out = _rapid_engine()(np.array(crop.convert("RGB")), use_det=False, use_cls=False, use_rec=True)
    return sanitize("".join(out.txts) if out.txts else "")


# --- Vision model via Ollama (local GPU) --------------------------------------


def ollama_vision_models(base_url: str) -> list[str] | None:
    """Installed Ollama models that can read images, or None if Ollama isn't
    reachable."""
    base_url = base_url.rstrip("/")
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=3) as resp:
            names = [m["name"] for m in json.loads(resp.read()).get("models", [])]
    except (OSError, ValueError, urllib.error.URLError):
        return None
    vision = []
    for name in names:
        try:
            info = _post_json(f"{base_url}/api/show", {"model": name}, timeout=5)
        except (OSError, ValueError, urllib.error.URLError):
            continue
        if "vision" in (info.get("capabilities") or []):
            vision.append(name)
    return vision


def read_ollama(image_path: Path, box: tuple[int, int, int, int], base_url: str, model: str) -> dict:
    body = {
        "model": model,
        "stream": False,
        "think": False,
        "format": _QUANTITY_SCHEMA,
        # num_predict: a quantity never needs more than a few tokens; without a
        # cap, glm-ocr looped on non-number crops until Ollama aborted with
        # HTTP 500 "token repeat limit reached" (4 of 78 reads).
        "options": {"temperature": 0, "num_predict": 32},
        "messages": [
            {"role": "user", "content": VLM_PROMPT, "images": [base64.b64encode(_crop_png(image_path, box)).decode()]}
        ],
    }
    data = _post_json(f"{base_url.rstrip('/')}/api/chat", body)
    try:
        quantity = json.loads(data["message"]["content"]).get("quantity", "")
    except (KeyError, ValueError):
        quantity = data.get("message", {}).get("content", "")
    return sanitize(quantity)


# --- Vision model via a cloud API (user's own key) ----------------------------


def read_api(
    image_path: Path, box: tuple[int, int, int, int], kind: str, base_url: str, model: str, api_key: str
) -> dict:
    image_b64 = base64.b64encode(_crop_png(image_path, box)).decode()
    instruction = VLM_PROMPT + " Reply with only the quantity, nothing else."
    if kind == "anthropic":
        data = _post_json(
            f"{(base_url or 'https://api.anthropic.com').rstrip('/')}/v1/messages",
            {
                "model": model,
                "max_tokens": 20,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                            {"type": "text", "text": instruction},
                        ],
                    }
                ],
            },
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        )
        text = "".join(block.get("text", "") for block in data.get("content", []))
    else:
        # Any OpenAI-compatible chat completions endpoint (OpenAI, OpenRouter,
        # LM Studio, a remote Ollama's /v1, ...).
        data = _post_json(
            f"{(base_url or 'https://api.openai.com/v1').rstrip('/')}/chat/completions",
            {
                "model": model,
                "max_tokens": 20,
                "temperature": 0,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                            {"type": "text", "text": instruction},
                        ],
                    }
                ],
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
        text = data["choices"][0]["message"]["content"] or ""
    return sanitize(text)
