import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import UPLOADS_DIR, get_db
from app.services import capture, icon_match_service
from app.services.errors_i18n import err

router = APIRouter(tags=["images"])

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}


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

    suffix = Path(file.filename or "").suffix or ".png"
    filename = f"{uuid.uuid4().hex}{suffix}"
    dest = UPLOADS_DIR / filename

    contents = await file.read()
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
def detect_stockpile(image_id: int, box: schemas.OcrCropRequest, lang: str = "pt-BR", db: Session = Depends(get_db)):
    image = crud.get_upload_image(db, image_id)
    if not image:
        raise HTTPException(status_code=404, detail=err("image_not_found", lang))
    if not icon_match_service.is_available():
        return schemas.StockpileDetectionOut(available=False, items=[])

    _chosen, _effective, reader = capture.resolve_reader(db)
    items = icon_match_service.detect_items(
        _image_path(image),
        (box.x, box.y, box.x + box.width, box.y + box.height),
        read_number=lambda path, number_box: capture.read_number(reader, path, number_box),
    )
    return schemas.StockpileDetectionOut(available=True, items=[schemas.DetectedStockItem(**i) for i in items])
