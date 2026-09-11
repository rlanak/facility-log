import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import UPLOADS_DIR, get_db
from app.services import ocr_service

router = APIRouter(tags=["images"])

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}


def _image_to_out(image) -> schemas.UploadImageOut:
    return schemas.UploadImageOut(
        id=image.id,
        building_id=image.building_id,
        url=f"/uploads/{Path(image.file_path).name}",
        uploaded_at=image.uploaded_at,
    )


@router.get("/api/buildings/{building_id}/images", response_model=list[schemas.UploadImageOut])
def list_building_images(building_id: int, db: Session = Depends(get_db)):
    if not crud.get_building(db, building_id):
        raise HTTPException(status_code=404, detail="Prédio não encontrado.")
    return [_image_to_out(img) for img in crud.get_building_images(db, building_id)]


@router.post("/api/buildings/{building_id}/images", response_model=schemas.UploadImageOut, status_code=201)
async def upload_building_image(building_id: int, file: UploadFile, db: Session = Depends(get_db)):
    if not crud.get_building(db, building_id):
        raise HTTPException(status_code=404, detail="Prédio não encontrado.")
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="Envie uma imagem PNG, JPEG ou WEBP.")

    suffix = Path(file.filename or "").suffix or ".png"
    filename = f"{uuid.uuid4().hex}{suffix}"
    dest = UPLOADS_DIR / filename

    contents = await file.read()
    dest.write_bytes(contents)

    image = crud.create_upload_image(db, building_id, str(dest))
    return _image_to_out(image)


@router.get("/api/ocr/status")
def ocr_status():
    return {"available": ocr_service.is_available()}


@router.post("/api/images/{image_id}/ocr", response_model=schemas.OcrResult)
def read_image_crop(image_id: int, box: schemas.OcrCropRequest, db: Session = Depends(get_db)):
    image = crud.get_upload_image(db, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Imagem não encontrada.")

    result = ocr_service.read_crop(
        Path(image.file_path), (box.x, box.y, box.x + box.width, box.y + box.height)
    )
    return schemas.OcrResult(**result)
