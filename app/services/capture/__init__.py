"""Which engine reads stockpile quantities from a screenshot — chosen by the
user in Configurações, stored in the app_settings table:

- "tesseract": the original OCR (needs Tesseract; bundled in the .exe).
- "rapidocr":  free local OCR (PaddleOCR models on onnxruntime, CPU) — much
               better than Tesseract on this font, no setup.
- "local_vlm": a vision model on the user's own GPU via Ollama.
- "api_vlm":   a vision model through a cloud API with the user's own key
               (Anthropic, or any OpenAI-compatible endpoint). Costs money
               per call, so never the default.

Whatever the engine, the value only pre-fills the form — the user confirms
before anything is saved (unchanged project rule). If the chosen engine is
unavailable (Ollama not running, no key), reading falls back to the best
local OCR and the status says so, rather than failing the whole capture.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from app import models
from app.services import ocr_service
from app.services.capture import readers

PROVIDERS = ("tesseract", "rapidocr", "local_vlm", "api_vlm")

DEFAULTS = {
    "capture_provider": "rapidocr",
    "ollama_url": "http://127.0.0.1:11434",
    "ollama_model": "",
    "api_kind": "anthropic",
    "api_base_url": "",
    "api_model": "claude-haiku-5-5",
    "api_key": "",
}


def get_settings(db: Session) -> dict:
    stored = {s.key: s.value for s in db.query(models.AppSetting).filter(models.AppSetting.key.in_(DEFAULTS))}
    return {key: stored.get(key, default) for key, default in DEFAULTS.items()}


def save_settings(db: Session, values: dict) -> None:
    for key, value in values.items():
        if key not in DEFAULTS:
            continue
        row = db.get(models.AppSetting, key)
        if row:
            row.value = value
        else:
            db.add(models.AppSetting(key=key, value=value))
    db.commit()


def provider_status(settings: dict, check_ollama: bool = True) -> dict:
    """{provider: {"available": bool, "detail": str}} plus the Ollama vision
    models found (for the settings dropdown)."""
    vision_models = readers.ollama_vision_models(settings["ollama_url"]) if check_ollama else None
    if vision_models is None:
        local_detail = "no_ollama"
    elif not vision_models:
        local_detail = "no_vision_model"
    elif settings["ollama_model"] not in vision_models:
        local_detail = "pick_model"
    else:
        local_detail = ""
    status = {
        "tesseract": {"available": ocr_service.is_available(), "detail": ""},
        "rapidocr": {"available": readers.rapidocr_available(), "detail": ""},
        "local_vlm": {"available": local_detail == "", "detail": local_detail},
        "api_vlm": {
            "available": bool(settings["api_key"] and settings["api_model"]),
            "detail": "" if settings["api_key"] else "no_key",
        },
    }
    return {"providers": status, "ollama_vision_models": vision_models or []}


def resolve_reader(db: Session) -> tuple[str, str, callable]:
    """(chosen provider, provider actually used, reader(image_path, box))."""
    settings = get_settings(db)
    chosen = settings["capture_provider"] if settings["capture_provider"] in PROVIDERS else DEFAULTS["capture_provider"]
    status = provider_status(settings, check_ollama=chosen == "local_vlm")["providers"]

    def reader_for(provider: str):
        if provider == "local_vlm":
            return lambda path, box: readers.read_ollama(path, box, settings["ollama_url"], settings["ollama_model"])
        if provider == "api_vlm":
            return lambda path, box: readers.read_api(
                path, box, settings["api_kind"], settings["api_base_url"], settings["api_model"], settings["api_key"]
            )
        if provider == "rapidocr":
            return readers.read_rapidocr
        return lambda path, box: ocr_service.read_crop(path, box, psm=11)

    for provider in (chosen, "rapidocr", "tesseract"):
        if status[provider]["available"]:
            return chosen, provider, reader_for(provider)
    return chosen, "", lambda path, box: {"available": False, "raw_text": "", "guess": ""}


def read_number(reader, image_path: Path, box: tuple[int, int, int, int]) -> dict:
    """Runs a reader, turning a network/engine failure into "couldn't read"
    instead of a 500 — the user can still type the value."""
    try:
        return reader(image_path, box)
    except Exception as exc:  # noqa: BLE001 - any engine failure is just "no read"
        return {"available": True, "raw_text": "", "guess": "", "error": str(exc)}
