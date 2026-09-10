from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

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
