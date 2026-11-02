from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.services import foxhole_data
from app.services.errors_i18n import err

router = APIRouter(prefix="/api/facilities", tags=["facilities"])


@router.get("", response_model=list[schemas.FacilityOut])
def list_facilities(db: Session = Depends(get_db)):
    return crud.get_facilities(db)


@router.post("", response_model=schemas.FacilityOut, status_code=201)
def create_facility(data: schemas.FacilityCreate, db: Session = Depends(get_db)):
    return crud.create_facility(db, data)


@router.get("/{facility_id}", response_model=schemas.FacilityOut)
def get_facility(facility_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    facility = crud.get_facility(db, facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    return facility


@router.put("/{facility_id}", response_model=schemas.FacilityOut)
def update_facility(facility_id: int, data: schemas.FacilityUpdate, lang: str = "pt-BR", db: Session = Depends(get_db)):
    facility = crud.get_facility(db, facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    return crud.update_facility(db, facility, data)


@router.delete("/{facility_id}", status_code=204)
def delete_facility(facility_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    facility = crud.get_facility(db, facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    crud.delete_facility(db, facility)


@router.get("/{facility_id}/stock", response_model=list[schemas.BuildingStockOut])
def get_facility_stock(facility_id: int, lang: str = "pt-BR", catalog_lang: str | None = None, db: Session = Depends(get_db)):
    facility = crud.get_facility(db, facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    stock = crud.get_current_stock_for_facility(db, facility_id)
    return [
        schemas.BuildingStockOut(
            building=building,
            entries=[
                schemas.StockEntryOut(
                    id=e.id,
                    resource_id=e.resource_id,
                    resource_name=crud.resolve_resource_name(e.resource, catalog_lang or lang),
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


@router.get("/{facility_id}/targets", response_model=list[schemas.TargetOut])
def list_targets(facility_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    if not crud.get_facility(db, facility_id):
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    by_key, by_id = crud.facility_stock_totals(db, facility_id)
    resources = {r.id: r for r in crud.resources_for_facility(db, facility_id)}
    result = []
    for resource_id, target in crud.get_facility_targets(db, facility_id).items():
        resource = resources.get(resource_id)
        if not resource:
            continue
        current = by_key.get(resource.resource_def_key, 0) if resource.resource_def_key else by_id.get(resource.id, 0)
        result.append(schemas.TargetOut(resource=resource, target_max=target, current=current))
    return result


@router.put("/{facility_id}/item-origins", status_code=204)
def set_item_origin(facility_id: int, data: schemas.ItemOriginSet, lang: str = "pt-BR", db: Session = Depends(get_db)):
    if not crud.get_facility(db, facility_id):
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    if not crud.get_resource(db, data.resource_id):
        raise HTTPException(status_code=404, detail=err("resource_not_found", lang))
    crud.set_item_origin(db, facility_id, data.resource_id, data.origin)


@router.put("/{facility_id}/targets", status_code=204)
def set_target(facility_id: int, data: schemas.TargetSet, lang: str = "pt-BR", db: Session = Depends(get_db)):
    if not crud.get_facility(db, facility_id):
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    if data.resource_id is not None:
        resource = crud.get_resource(db, data.resource_id)
    elif data.resource_def_key and foxhole_data.get_resource_def(data.resource_def_key):
        name = foxhole_data.resource_display_name(data.resource_def_key, "en-US")
        resource = crud.get_or_create_resource(db, name, data.resource_def_key)
    else:
        resource = None
    if not resource:
        raise HTTPException(status_code=404, detail=err("resource_not_found", lang))
    crud.set_facility_target(db, facility_id, resource, data.target_max)
