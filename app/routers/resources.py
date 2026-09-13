from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.services.errors_i18n import err

router = APIRouter(prefix="/api/resources", tags=["resources"])


@router.get("", response_model=list[schemas.ResourceOut])
def list_resources(db: Session = Depends(get_db)):
    return crud.get_resources(db)


@router.post("", response_model=schemas.ResourceOut, status_code=201)
def create_resource(data: schemas.ResourceCreate, lang: str = "pt-BR", db: Session = Depends(get_db)):
    if crud.get_resource_by_name(db, data.name):
        raise HTTPException(status_code=409, detail=err("resource_name_exists", lang))
    return crud.create_resource(db, data)


@router.put("/{resource_id}", response_model=schemas.ResourceOut)
def update_resource(resource_id: int, data: schemas.ResourceUpdate, lang: str = "pt-BR", db: Session = Depends(get_db)):
    resource = crud.get_resource(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail=err("resource_not_found", lang))
    return crud.update_resource(db, resource, data)


@router.delete("/{resource_id}", status_code=204)
def delete_resource(resource_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    resource = crud.get_resource(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail=err("resource_not_found", lang))
    if crud.resource_in_use(db, resource_id):
        raise HTTPException(status_code=409, detail=err("resource_in_use", lang))
    crud.delete_resource(db, resource)
