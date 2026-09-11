from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(prefix="/api/facilities", tags=["facilities"])


@router.get("", response_model=list[schemas.FacilityOut])
def list_facilities(db: Session = Depends(get_db)):
    return crud.get_facilities(db)


@router.post("", response_model=schemas.FacilityOut, status_code=201)
def create_facility(data: schemas.FacilityCreate, db: Session = Depends(get_db)):
    return crud.create_facility(db, data)


@router.get("/{facility_id}", response_model=schemas.FacilityOut)
def get_facility(facility_id: int, db: Session = Depends(get_db)):
    facility = crud.get_facility(db, facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail="Facility não encontrada.")
    return facility


@router.put("/{facility_id}", response_model=schemas.FacilityOut)
def update_facility(facility_id: int, data: schemas.FacilityUpdate, db: Session = Depends(get_db)):
    facility = crud.get_facility(db, facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail="Facility não encontrada.")
    return crud.update_facility(db, facility, data)


@router.delete("/{facility_id}", status_code=204)
def delete_facility(facility_id: int, db: Session = Depends(get_db)):
    facility = crud.get_facility(db, facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail="Facility não encontrada.")
    crud.delete_facility(db, facility)


@router.get("/{facility_id}/stock", response_model=list[schemas.BuildingStockOut])
def get_facility_stock(facility_id: int, db: Session = Depends(get_db)):
    facility = crud.get_facility(db, facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail="Facility não encontrada.")
    stock = crud.get_current_stock_for_facility(db, facility_id)
    return [
        schemas.BuildingStockOut(
            building=building,
            entries=[
                schemas.StockEntryOut(
                    id=e.id,
                    resource_id=e.resource_id,
                    resource_name=e.resource.display_name,
                    resource_icon=e.resource.icon,
                    quantity=e.quantity,
                    source=e.source,
                    recorded_at=e.recorded_at,
                )
                for e in entries
            ],
        )
        for building, entries in stock.items()
    ]
