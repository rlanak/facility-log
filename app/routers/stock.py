from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(tags=["stock"])


@router.get("/api/buildings/{building_id}/stock", response_model=list[schemas.StockEntryOut])
def get_building_stock(building_id: int, db: Session = Depends(get_db)):
    if not crud.get_building(db, building_id):
        raise HTTPException(status_code=404, detail="Prédio não encontrado.")
    entries = crud.get_current_stock_for_building(db, building_id)
    return [
        schemas.StockEntryOut(
            id=e.id,
            resource_id=e.resource_id,
            resource_name=e.resource.name,
            resource_icon=e.resource.icon,
            quantity=e.quantity,
            source=e.source,
            recorded_at=e.recorded_at,
        )
        for e in entries
    ]


@router.post("/api/buildings/{building_id}/stock", response_model=list[schemas.StockEntryOut], status_code=201)
def add_building_stock(building_id: int, entries: list[schemas.StockEntryIn], db: Session = Depends(get_db)):
    if not crud.get_building(db, building_id):
        raise HTTPException(status_code=404, detail="Prédio não encontrado.")
    try:
        created = crud.add_stock_entries(db, building_id, entries)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return [
        schemas.StockEntryOut(
            id=e.id,
            resource_id=e.resource_id,
            resource_name=e.resource.name,
            resource_icon=e.resource.icon,
            quantity=e.quantity,
            source=e.source,
            recorded_at=e.recorded_at,
        )
        for e in created
    ]
