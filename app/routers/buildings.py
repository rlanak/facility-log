from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.services import production

router = APIRouter(tags=["buildings"])


@router.get("/api/facilities/{facility_id}/buildings", response_model=list[schemas.BuildingOut])
def list_buildings(facility_id: int, db: Session = Depends(get_db)):
    if not crud.get_facility(db, facility_id):
        raise HTTPException(status_code=404, detail="Facility não encontrada.")
    return crud.get_buildings(db, facility_id)


@router.post("/api/facilities/{facility_id}/buildings", response_model=schemas.BuildingOut, status_code=201)
def create_building(facility_id: int, data: schemas.BuildingCreate, db: Session = Depends(get_db)):
    if not crud.get_facility(db, facility_id):
        raise HTTPException(status_code=404, detail="Facility não encontrada.")
    if not data.name and not data.building_type_key:
        raise HTTPException(status_code=422, detail="Informe um nome ou selecione um tipo do Foxhole.")
    return crud.create_building(db, facility_id, data)


@router.get("/api/buildings/{building_id}", response_model=schemas.BuildingOut)
def get_building(building_id: int, db: Session = Depends(get_db)):
    building = crud.get_building(db, building_id)
    if not building:
        raise HTTPException(status_code=404, detail="Prédio não encontrado.")
    return building


@router.put("/api/buildings/{building_id}", response_model=schemas.BuildingOut)
def update_building(building_id: int, data: schemas.BuildingUpdate, db: Session = Depends(get_db)):
    building = crud.get_building(db, building_id)
    if not building:
        raise HTTPException(status_code=404, detail="Prédio não encontrado.")
    return crud.update_building(db, building, data)


@router.delete("/api/buildings/{building_id}", status_code=204)
def delete_building(building_id: int, db: Session = Depends(get_db)):
    building = crud.get_building(db, building_id)
    if not building:
        raise HTTPException(status_code=404, detail="Prédio não encontrado.")
    crud.delete_building(db, building)


@router.put("/api/buildings/{building_id}/production", response_model=schemas.BuildingOut)
def set_building_production(building_id: int, data: schemas.BuildingProductionUpdate, db: Session = Depends(get_db)):
    building = crud.get_building(db, building_id)
    if not building:
        raise HTTPException(status_code=404, detail="Prédio não encontrado.")
    if data.recipe_key and not building.building_type_key:
        raise HTTPException(status_code=422, detail="Este prédio não está vinculado a um tipo do Foxhole.")
    return crud.update_building_production(db, building, data)


@router.get("/api/buildings/{building_id}/production-estimate", response_model=schemas.ProductionEstimateOut | None)
def get_production_estimate(building_id: int, db: Session = Depends(get_db)):
    building = crud.get_building(db, building_id)
    if not building:
        raise HTTPException(status_code=404, detail="Prédio não encontrado.")
    if not building.building_type_key or not building.active_recipe_key:
        return None
    return production.estimate_production(
        building.building_type_key, building.active_recipe_key, building.queue_count, datetime.now()
    )
