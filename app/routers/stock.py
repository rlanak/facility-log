from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import auth, crud, schemas
from app.database import get_db
from app.services.errors_i18n import err

router = APIRouter(tags=["stock"])


@router.get("/api/buildings/{building_id}/stock", response_model=list[schemas.StockEntryOut])
def get_building_stock(building_id: int, lang: str = "pt-BR", catalog_lang: str | None = None, db: Session = Depends(get_db)):
    if not crud.get_building(db, building_id):
        raise HTTPException(status_code=404, detail=err("building_not_found", lang))
    entries = crud.get_current_stock_for_building(db, building_id)
    return [
        schemas.StockEntryOut(
            id=e.id,
            resource_id=e.resource_id,
            resource_name=crud.resolve_resource_name(e.resource, catalog_lang or lang),
            resource_icon=e.resource.icon,
            quantity=e.quantity,
            storage=e.storage,
            source=e.source,
            recorded_at=e.recorded_at,
            created_by_name=e.created_by.name if e.created_by else None,
        )
        for e in entries
    ]


@router.post("/api/buildings/{building_id}/stock", response_model=list[schemas.StockEntryOut], status_code=201)
def add_building_stock(
    building_id: int,
    entries: list[schemas.StockEntryIn],
    request: Request,
    lang: str = "pt-BR",
    catalog_lang: str | None = None,
    db: Session = Depends(get_db),
):
    if not crud.get_building(db, building_id):
        raise HTTPException(status_code=404, detail=err("building_not_found", lang))
    try:
        created = crud.add_stock_entries(db, building_id, entries, lang, catalog_lang, created_by_id=auth.current_user_id(request))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return [
        schemas.StockEntryOut(
            id=e.id,
            resource_id=e.resource_id,
            resource_name=crud.resolve_resource_name(e.resource, catalog_lang or lang),
            resource_icon=e.resource.icon,
            quantity=e.quantity,
            storage=e.storage,
            source=e.source,
            recorded_at=e.recorded_at,
            created_by_name=e.created_by.name if e.created_by else None,
        )
        for e in created
    ]


@router.delete("/api/buildings/{building_id}/stock/{resource_id}", status_code=204)
def delete_building_stock_item(
    building_id: int,
    resource_id: int,
    storage: str = "normal",
    lang: str = "pt-BR",
    db: Session = Depends(get_db),
):
    if not crud.get_building(db, building_id):
        raise HTTPException(status_code=404, detail=err("building_not_found", lang))
    crud.delete_stock_entries(db, building_id, resource_id, storage)
