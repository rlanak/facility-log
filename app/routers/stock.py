from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
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
        )
        for e in entries
    ]


@router.post("/api/buildings/{building_id}/stock", response_model=list[schemas.StockEntryOut], status_code=201)
def add_building_stock(
    building_id: int,
    entries: list[schemas.StockEntryIn],
    lang: str = "pt-BR",
    catalog_lang: str | None = None,
    db: Session = Depends(get_db),
):
    if not crud.get_building(db, building_id):
        raise HTTPException(status_code=404, detail=err("building_not_found", lang))
    try:
        created = crud.add_stock_entries(db, building_id, entries, lang, catalog_lang)
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
        )
        for e in created
    ]
