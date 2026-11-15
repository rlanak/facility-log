"""Which engine reads stockpile quantities from a screenshot on the server —
chosen in Configurações. Local mode keeps one choice for the app
(app_settings). On the web it is each person's own (user_settings,
14/11/2026): it was shared, so one member's paid API key read everyone's
screenshots and any member could change what the others used.

- "rapidocr":  free local OCR (PaddleOCR models on onnxruntime, CPU), no setup.
- "local_vlm": a vision model through Ollama on the machine running the app.
               That's the user's own PC in local mode; on a web server it's
               hidden (a server rarely has a GPU) unless
               FACILITY_LOG_SERVER_OLLAMA=1. Web users can instead have their
               *browser* read with the AI on their own PC (web/js/personalAI.js).
- "api_vlm":   a vision model through a cloud API with the user's own key
               (Anthropic, or any OpenAI-compatible endpoint). Costs money
               per call, so never the default.

Whatever the engine, the value only pre-fills the form — the user confirms
before anything is saved (unchanged project rule). If the chosen engine is
unavailable (Ollama not running, no key), reading falls back to RapidOCR and
the status says so, rather than failing the whole capture.
"""

import os
from pathlib import Path

from sqlalchemy.orm import Session

from app import models
from app.services.capture import readers

PROVIDERS = ("rapidocr", "local_vlm", "api_vlm")


def server_local_ai_allowed() -> bool:
    """Ollama on the server only makes sense where the server is the user's
    own PC (local mode), or where the operator says the server has one."""
    from app import auth

    return not auth.config.enabled or os.environ.get("FACILITY_LOG_SERVER_OLLAMA", "").strip() == "1"


def effective_provider_choice(settings: dict) -> str:
    """The saved choice, with a hidden server Ollama read as RapidOCR."""
    chosen = settings["capture_provider"] if settings["capture_provider"] in PROVIDERS else DEFAULTS["capture_provider"]
    if chosen == "local_vlm" and not server_local_ai_allowed():
        return DEFAULTS["capture_provider"]
    return chosen

DEFAULTS = {
    "capture_provider": "rapidocr",
    "ollama_url": "http://127.0.0.1:11434",
    "ollama_model": "",
    "api_kind": "anthropic",
    "api_base_url": "",
    "api_model": "claude-haiku-5-5",
    "api_key": "",
}


def ollama_url_locked() -> bool:
    """On the web the server's Ollama address is the operator's to set
    (FACILITY_LOG_OLLAMA_URL), never a member's: the server calls it, and
    it is normally a private address — exactly what a member must not be
    able to choose (see netguard)."""
    from app import auth

    return auth.config.enabled


def _personal() -> bool:
    from app import auth

    return auth.config.enabled


def get_settings(db: Session, user_id: int | None = None) -> dict:
    """`user_id`: whose settings, on the web (nobody = the defaults)."""
    if _personal():
        rows = (
            db.query(models.UserSetting).filter(
                models.UserSetting.user_id == user_id, models.UserSetting.key.in_(DEFAULTS)
            )
            if user_id is not None
            else []
        )
    else:
        rows = db.query(models.AppSetting).filter(models.AppSetting.key.in_(DEFAULTS))
    stored = {s.key: s.value for s in rows}
    settings = {key: stored.get(key, default) for key, default in DEFAULTS.items()}
    if ollama_url_locked():
        settings["ollama_url"] = os.environ.get("FACILITY_LOG_OLLAMA_URL", "").strip() or DEFAULTS["ollama_url"]
    return settings


def save_settings(db: Session, values: dict, user_id: int | None = None) -> None:
    personal = _personal()
    if personal and user_id is None:
        return
    for key, value in values.items():
        if key not in DEFAULTS:
            continue
        row = db.get(models.UserSetting, (user_id, key)) if personal else db.get(models.AppSetting, key)
        if row:
            row.value = value
        elif personal:
            db.add(models.UserSetting(user_id=user_id, key=key, value=value))
        else:
            db.add(models.AppSetting(key=key, value=value))
    db.commit()


def provider_status(settings: dict, check_ollama: bool = True) -> dict:
    """{provider: {"available": bool, "detail": str}} plus the Ollama vision
    models found (for the settings dropdown)."""
    allowed = server_local_ai_allowed()
    vision_models = readers.ollama_vision_models(settings["ollama_url"]) if check_ollama and allowed else None
    if not allowed:
        local_detail = "server_hidden"
    elif vision_models is None:
        local_detail = "no_ollama"
    elif not vision_models:
        local_detail = "no_vision_model"
    elif settings["ollama_model"] not in vision_models:
        local_detail = "pick_model"
    else:
        local_detail = ""
    status = {
        "rapidocr": {"available": readers.rapidocr_available(), "detail": ""},
        "local_vlm": {"available": local_detail == "", "detail": local_detail},
        "api_vlm": {
            "available": bool(settings["api_key"] and settings["api_model"]),
            "detail": "" if settings["api_key"] else "no_key",
        },
    }
    return {"providers": status, "ollama_vision_models": vision_models or [], "server_local_ai": allowed}


def resolve_reader(db: Session, user_id: int | None = None) -> tuple[str, str, callable]:
    """(chosen provider, provider actually used, reader(image_path, box)) —
    on the web, for the person who asked."""
    settings = get_settings(db, user_id)
    chosen = effective_provider_choice(settings)
    status = provider_status(settings, check_ollama=chosen == "local_vlm")["providers"]

    def reader_for(provider: str):
        if provider == "local_vlm":
            return lambda path, box: readers.read_ollama(path, box, settings["ollama_url"], settings["ollama_model"])
        if provider == "api_vlm":
            return lambda path, box: readers.read_api(
                path, box, settings["api_kind"], settings["api_base_url"], settings["api_model"], settings["api_key"]
            )
        return readers.read_rapidocr

    for provider in (chosen, "rapidocr"):
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
