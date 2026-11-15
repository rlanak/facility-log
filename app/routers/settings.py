from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import auth, schemas
from app.database import get_db
from app.services import capture, netguard
from app.services.errors_i18n import err

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _to_out(db: Session, user_id: int | None) -> schemas.CaptureSettingsOut:
    settings = capture.get_settings(db, user_id)
    status = capture.provider_status(settings)
    key = settings["api_key"]
    return schemas.CaptureSettingsOut(
        capture_provider=capture.effective_provider_choice(settings),
        ollama_url=settings["ollama_url"],
        ollama_model=settings["ollama_model"],
        api_kind=settings["api_kind"],
        api_base_url=settings["api_base_url"],
        api_model=settings["api_model"],
        # The key itself never goes back to the browser — just whether one is
        # set and its last 4 characters, to tell keys apart.
        api_key_set=bool(key),
        api_key_hint=f"…{key[-4:]}" if len(key) >= 8 else "",
        providers=status["providers"],
        ollama_vision_models=status["ollama_vision_models"],
        server_local_ai=status["server_local_ai"],
    )


@router.get("/capture", response_model=schemas.CaptureSettingsOut)
def get_capture_settings(request: Request, db: Session = Depends(get_db)):
    return _to_out(db, auth.current_user_id(request))


def _valid_url(url: str | None) -> bool:
    return not url or url.strip().lower().startswith(("http://", "https://"))


@router.put("/capture", response_model=schemas.CaptureSettingsOut)
def update_capture_settings(
    request: Request, data: schemas.CaptureSettingsIn, lang: str = "pt-BR", db: Session = Depends(get_db)
):
    user_id = auth.current_user_id(request)
    values = data.model_dump(exclude_unset=True, exclude={"api_key", "clear_api_key"})
    if not _valid_url(values.get("api_base_url")) or not _valid_url(values.get("ollama_url")):
        raise HTTPException(status_code=422, detail=err("invalid_url", lang))
    current = capture.get_settings(db, user_id)
    # Security (14/11/2026): the server calls these addresses, and on the web
    # any member can save them. Only public addresses there (netguard), and
    # the server's Ollama address isn't a setting at all.
    if capture.ollama_url_locked():
        values.pop("ollama_url", None)
    if "api_base_url" in values and values["api_base_url"]:
        try:
            netguard.check_url(values["api_base_url"])
        except netguard.BlockedAddress:
            raise HTTPException(status_code=422, detail=err("private_url", lang))
    if values.get("capture_provider") not in (None, *capture.PROVIDERS) or (
        values.get("capture_provider") == "local_vlm" and not capture.server_local_ai_allowed()
    ):
        values.pop("capture_provider")
    # Security (08/11/2026): the saved key is sent to api_base_url. Pointing
    # it somewhere else (or switching the API kind) without typing the key
    # again would hand the key to that address — so that drops the saved key
    # instead. (Settings were shared by everyone then; they are each
    # person's own on the web now, and the rule still costs nothing.)
    moved = any(
        k in values and (values[k] or "") != (current.get(k) or "") for k in ("api_base_url", "api_kind")
    )
    # An empty key field means "keep the current key", not "erase it".
    if data.clear_api_key or (moved and not data.api_key):
        values["api_key"] = ""
    elif data.api_key:
        values["api_key"] = data.api_key.strip()
    capture.save_settings(db, {k: (v or "") for k, v in values.items()}, user_id)
    return _to_out(db, user_id)
