from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.services import capture

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _to_out(db: Session) -> schemas.CaptureSettingsOut:
    settings = capture.get_settings(db)
    status = capture.provider_status(settings)
    key = settings["api_key"]
    return schemas.CaptureSettingsOut(
        capture_provider=settings["capture_provider"],
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
    )


@router.get("/capture", response_model=schemas.CaptureSettingsOut)
def get_capture_settings(db: Session = Depends(get_db)):
    return _to_out(db)


@router.put("/capture", response_model=schemas.CaptureSettingsOut)
def update_capture_settings(data: schemas.CaptureSettingsIn, db: Session = Depends(get_db)):
    values = data.model_dump(exclude_unset=True, exclude={"api_key", "clear_api_key"})
    if values.get("capture_provider") not in (None, *capture.PROVIDERS):
        values.pop("capture_provider")
    # An empty key field means "keep the current key", not "erase it".
    if data.clear_api_key:
        values["api_key"] = ""
    elif data.api_key:
        values["api_key"] = data.api_key.strip()
    capture.save_settings(db, {k: (v or "") for k, v in values.items()})
    return _to_out(db)
