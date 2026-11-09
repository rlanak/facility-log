"""Private production orders — see app/services/private_orders.py.

Every path sits under /api/buildings/{id} or /api/facilities/{id}, so the
private-facility check in auth.gate already covers them."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import auth, crud, models, schemas
from app.database import get_db
from app.services import foxhole_data, private_orders
from app.services.errors_i18n import err

router = APIRouter(tags=["private-orders"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _building(db: Session, building_id: int, lang: str) -> models.Building:
    building = crud.get_building(db, building_id)
    if not building:
        raise HTTPException(status_code=404, detail=err("building_not_found", lang))
    if not building.building_type_key:
        raise HTTPException(status_code=422, detail=err("building_not_linked", lang))
    return building


def _order(db: Session, building: models.Building, order_id: int, lang: str) -> models.PrivateOrder:
    order = db.get(models.PrivateOrder, order_id)
    if not order or order.building_id != building.id:
        raise HTTPException(status_code=404, detail=err("private_order_not_found", lang))
    return order


def _apply(order: models.PrivateOrder, data: schemas.PrivateOrderIn, building: models.Building, request: Request, lang: str):
    recipe = foxhole_data.get_recipe(building.building_type_key, data.recipe_key)
    if not recipe:
        raise HTTPException(status_code=422, detail=err("recipe_not_in_building", lang))
    allowed = {io["resource"] for io in private_orders.solid_inputs(recipe)}
    inputs = {}
    for key, qty in data.inputs.items():
        if key not in allowed:
            continue
        if qty is None or qty < 0 or qty > 1_000_000:
            raise HTTPException(status_code=422, detail=err("invalid_quantity", lang))
        inputs[key] = float(qty)
    if data.cycle_left_seconds < 0 or data.cycle_left_seconds > recipe["time_seconds"]:
        raise HTTPException(status_code=422, detail=err("invalid_quantity", lang))
    owner = data.owner_name.strip()
    if not owner:
        user = getattr(request.state, "user", None)
        owner = user.name if user else "?"
    order.owner_name = owner[:100]
    order.recipe_key = data.recipe_key
    order.inputs_json = json.dumps(inputs)
    order.cycle_left_seconds = data.cycle_left_seconds
    started = data.started_at or _now()
    order.started_at = started if started.tzinfo else started.replace(tzinfo=timezone.utc)


def _check_queues(db: Session, building: models.Building, lang: str, exclude_id: int | None = None):
    """A new/edited running private order needs a free queue: public queues
    + private ones still producing can't pass the building's limit."""
    building_type = foxhole_data.get_building_type(building.building_type_key)
    if not building_type:
        return
    now = _now()
    public = sum(s["queue_count"] for s in building.production_slots or [])
    private = sum(
        1
        for o in private_orders.open_orders(db, building)
        if o.id != exclude_id and private_orders.compute(o, building, now)["status"] == "running"
    )
    if public + private + 1 > building_type["queue_slots"]:
        raise HTTPException(
            status_code=422,
            detail=err("queue_slots_with_private", lang, public=public, private=private + 1, max=building_type["queue_slots"]),
        )


@router.get("/api/facilities/{facility_id}/private-orders")
def list_facility_orders(facility_id: int, lang: str = "pt-BR", catalog_lang: str | None = None, db: Session = Depends(get_db)):
    if not crud.get_facility(db, facility_id):
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    return private_orders.for_facility(db, facility_id, _now(), catalog_lang or lang)


@router.post("/api/buildings/{building_id}/private-orders", status_code=201)
def create_order(
    building_id: int,
    data: schemas.PrivateOrderIn,
    request: Request,
    lang: str = "pt-BR",
    catalog_lang: str | None = None,
    db: Session = Depends(get_db),
):
    building = _building(db, building_id, lang)
    order = models.PrivateOrder(building_id=building.id, created_by_id=auth.current_user_id(request))
    _apply(order, data, building, request, lang)
    if private_orders.compute(order, building, _now())["status"] == "running":
        _check_queues(db, building, lang)
    db.add(order)
    db.commit()
    db.refresh(order)
    return private_orders.compute(order, building, _now(), catalog_lang or lang)


@router.put("/api/buildings/{building_id}/private-orders/{order_id}")
def update_order(
    building_id: int,
    order_id: int,
    data: schemas.PrivateOrderIn,
    request: Request,
    lang: str = "pt-BR",
    catalog_lang: str | None = None,
    db: Session = Depends(get_db),
):
    building = _building(db, building_id, lang)
    order = _order(db, building, order_id, lang)
    _apply(order, data, building, request, lang)
    if private_orders.compute(order, building, _now())["status"] == "running":
        _check_queues(db, building, lang, exclude_id=order.id)
    db.commit()
    db.refresh(order)
    return private_orders.compute(order, building, _now(), catalog_lang or lang)


@router.post("/api/buildings/{building_id}/private-orders/{order_id}/close", status_code=204)
def close_order(building_id: int, order_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    """Output retrieved (and, if wanted, logged where it went — the browser
    does that with the normal stock endpoint before calling this)."""
    building = _building(db, building_id, lang)
    order = _order(db, building, order_id, lang)
    order.closed_at = _now()
    db.commit()


@router.delete("/api/buildings/{building_id}/private-orders/{order_id}", status_code=204)
def delete_order(building_id: int, order_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    """Logged by mistake: gone, no trace."""
    building = _building(db, building_id, lang)
    order = _order(db, building, order_id, lang)
    db.delete(order)
    db.commit()
