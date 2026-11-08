import io
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import UPLOADS_DIR, get_db
from app.services import capture, foxhole_data, icon_match_service
from app.services.errors_i18n import err

router = APIRouter(tags=["images"])

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
# Security (08/11/2026): the file is decoded and only a real PNG/JPEG/WEBP is
# kept, saved with the extension of what it actually is. The client's
# filename/content type are never trusted: "x.html" sent as image/png used to
# be saved as .html and served from /uploads as a same-origin page (stored
# XSS). Size/pixel caps keep one upload from eating the server's memory.
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
_FORMAT_SUFFIX = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}


def _image_suffix(contents: bytes) -> str | None:
    """The extension for this image's real format, or None if it isn't a
    PNG/JPEG/WEBP within the limits."""
    from PIL import Image

    try:
        with Image.open(io.BytesIO(contents)) as img:
            if img.format not in _FORMAT_SUFFIX or img.width * img.height > MAX_IMAGE_PIXELS:
                return None
            img.verify()
            return _FORMAT_SUFFIX[img.format]
    except Exception:
        return None


def _image_path(image) -> Path:
    # file_path is stored absolute; if the app folder moved since upload
    # (it did once), fall back to the same
    # file name under the current uploads folder.
    path = Path(image.file_path)
    return path if path.is_file() else UPLOADS_DIR / path.name


def _image_to_out(image) -> schemas.UploadImageOut:
    return schemas.UploadImageOut(
        id=image.id,
        building_id=image.building_id,
        url=f"/uploads/{Path(image.file_path).name}",
        uploaded_at=image.uploaded_at,
    )


@router.get("/api/buildings/{building_id}/images", response_model=list[schemas.UploadImageOut])
def list_building_images(building_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    if not crud.get_building(db, building_id):
        raise HTTPException(status_code=404, detail=err("building_not_found", lang))
    return [_image_to_out(img) for img in crud.get_building_images(db, building_id)]


@router.post("/api/buildings/{building_id}/images", response_model=schemas.UploadImageOut, status_code=201)
async def upload_building_image(building_id: int, file: UploadFile, lang: str = "pt-BR", db: Session = Depends(get_db)):
    if not crud.get_building(db, building_id):
        raise HTTPException(status_code=404, detail=err("building_not_found", lang))
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail=err("invalid_image_type", lang))

    contents = await file.read(MAX_IMAGE_BYTES + 1)
    suffix = _image_suffix(contents) if len(contents) <= MAX_IMAGE_BYTES else None
    if not suffix:
        raise HTTPException(status_code=422, detail=err("invalid_image_type", lang))
    filename = f"{uuid.uuid4().hex}{suffix}"
    dest = UPLOADS_DIR / filename
    dest.write_bytes(contents)

    image = crud.create_upload_image(db, building_id, str(dest))
    return _image_to_out(image)


@router.get("/api/ocr/status")
def ocr_status(db: Session = Depends(get_db)):
    chosen, effective, _reader = capture.resolve_reader(db)
    return {
        "available": bool(effective),
        # The engine picked in Configurações vs the one that will actually
        # read (differs when the chosen one is unavailable, e.g. Ollama off).
        "provider": chosen,
        "effective_provider": effective,
        "stockpile_detect_available": icon_match_service.is_available(),
    }


@router.post("/api/images/{image_id}/ocr", response_model=schemas.OcrResult)
def read_image_crop(image_id: int, box: schemas.OcrCropRequest, lang: str = "pt-BR", db: Session = Depends(get_db)):
    image = crud.get_upload_image(db, image_id)
    if not image:
        raise HTTPException(status_code=404, detail=err("image_not_found", lang))

    _chosen, _effective, reader = capture.resolve_reader(db)
    result = capture.read_number(reader, _image_path(image), (box.x, box.y, box.x + box.width, box.y + box.height))
    return schemas.OcrResult(**result)


@router.post("/api/images/{image_id}/detect-stockpile", response_model=schemas.StockpileDetectionOut)
def detect_stockpile(
    image_id: int, box: schemas.OcrCropRequest, read: bool = True, lang: str = "pt-BR", db: Session = Depends(get_db)
):
    """read=false: find the items only — the browser reads the numbers with
    the AI on the user's own PC (web/js/personalAI.js)."""
    image = crud.get_upload_image(db, image_id)
    if not image:
        raise HTTPException(status_code=404, detail=err("image_not_found", lang))
    if not icon_match_service.is_available():
        return schemas.StockpileDetectionOut(available=False, items=[])

    read_number = None
    if read:
        _chosen, _effective, reader = capture.resolve_reader(db)
        read_number = lambda path, number_box: capture.read_number(reader, path, number_box)  # noqa: E731
    items = icon_match_service.detect_items(
        _image_path(image), (box.x, box.y, box.x + box.width, box.y + box.height), read_number=read_number
    )
    return schemas.StockpileDetectionOut(available=True, items=[schemas.DetectedStockItem(**i) for i in items])


@router.post("/api/images/{image_id}/exemplars", status_code=204)
def save_icon_exemplars(image_id: int, items: list[schemas.IconExemplarIn], lang: str = "pt-BR", db: Session = Depends(get_db)):
    """Slots the user confirmed after auto-detection become real exemplars of
    their item — how the detector learns to tell near-identical icons apart
    (Assembly Materials tiers). See icon_match_service.add_exemplar."""
    image = crud.get_upload_image(db, image_id)
    if not image:
        raise HTTPException(status_code=404, detail=err("image_not_found", lang))
    path = _image_path(image)
    for item in items:
        if not foxhole_data.get_resource_def(item.resource_def_key) or item.box_width < 8 or item.box_height < 8:
            continue
        icon_match_service.add_exemplar(
            path, (item.box_x, item.box_y, item.box_x + item.box_width, item.box_y + item.box_height), item.resource_def_key
        )
