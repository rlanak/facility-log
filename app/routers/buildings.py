from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.services import foxhole_data, production
from app.services.errors_i18n import err

router = APIRouter(tags=["buildings"])


@router.get("/api/facilities/{facility_id}/buildings", response_model=list[schemas.BuildingOut])
def list_buildings(facility_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    if not crud.get_facility(db, facility_id):
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    return crud.get_buildings(db, facility_id)


@router.post("/api/facilities/{facility_id}/buildings", response_model=schemas.BuildingOut, status_code=201)
def create_building(facility_id: int, data: schemas.BuildingCreate, lang: str = "pt-BR", db: Session = Depends(get_db)):
    if not crud.get_facility(db, facility_id):
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    if not data.name and not data.building_type_key:
        raise HTTPException(status_code=422, detail=err("need_name_or_type", lang))
    return crud.create_building(db, facility_id, data)


@router.get("/api/buildings/{building_id}", response_model=schemas.BuildingOut)
def get_building(building_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    building = crud.get_building(db, building_id)
    if not building:
        raise HTTPException(status_code=404, detail=err("building_not_found", lang))
    return building


@router.put("/api/buildings/{building_id}", response_model=schemas.BuildingOut)
def update_building(building_id: int, data: schemas.BuildingUpdate, lang: str = "pt-BR", db: Session = Depends(get_db)):
    building = crud.get_building(db, building_id)
    if not building:
        raise HTTPException(status_code=404, detail=err("building_not_found", lang))
    return crud.update_building(db, building, data)


@router.delete("/api/buildings/{building_id}", status_code=204)
def delete_building(building_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    building = crud.get_building(db, building_id)
    if not building:
        raise HTTPException(status_code=404, detail=err("building_not_found", lang))
    crud.delete_building(db, building)


@router.put("/api/buildings/{building_id}/production", response_model=schemas.BuildingOut)
def set_building_production(
    building_id: int, data: schemas.BuildingProductionUpdate, lang: str = "pt-BR", db: Session = Depends(get_db)
):
    building = crud.get_building(db, building_id)
    if not building:
        raise HTTPException(status_code=404, detail=err("building_not_found", lang))
    if data.slots and not building.building_type_key:
        raise HTTPException(status_code=422, detail=err("building_not_linked", lang))
    building_type = foxhole_data.get_building_type(building.building_type_key) if building.building_type_key else None
    total_queues = sum(slot.queue_count for slot in data.slots)
    if building_type and total_queues > building_type["queue_slots"]:
        raise HTTPException(status_code=422, detail=err("queue_slots_exceeded", lang))
    return crud.update_building_production(db, building, data)


@router.get("/api/buildings/{building_id}/production-estimate", response_model=list[schemas.ProductionEstimateOut])
def get_production_estimate(
    building_id: int, lang: str = "pt-BR", catalog_lang: str | None = None, db: Session = Depends(get_db)
):
    building = crud.get_building(db, building_id)
    if not building:
        raise HTTPException(status_code=404, detail=err("building_not_found", lang))
    if not building.building_type_key or not building.production_slots:
        return []
    current_stock = crud.get_current_stock_by_resource_def(db, building_id)
    return production.estimate_building_slots(
        building.building_type_key,
        building.production_slots,
        current_stock,
        datetime.now(),
        catalog_lang or lang,
        crud.unlimited_resource_keys(crud.get_resources(db)),
    )
