from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db
from app.services import discord_dashboard, foxhole_data, projection
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


@router.get("/{facility_id}/dashboard")
def dashboard(facility_id: int, lang: str = "pt-BR", catalog_lang: str | None = None, db: Session = Depends(get_db)):
    """Live estimate for the dashboard tab — see app/services/projection.py.
    Read only: nothing here is stored."""
    if not crud.get_facility(db, facility_id):
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    return projection.facility_dashboard(db, facility_id, datetime.now(timezone.utc), catalog_lang or lang)


class WebhookIn(BaseModel):
    url: str


def _webhook_status(hook: models.FacilityWebhook | None) -> dict:
    """Never the URL itself: it works like a password for the channel."""
    if not hook:
        return {"configured": False, "interval_seconds": discord_dashboard.INTERVAL_SECONDS}
    token = hook.url.rstrip("/").rsplit("/", 1)[-1]
    return {
        "configured": True,
        "url_hint": f"…{token[-4:]}",
        "message_id": hook.message_id,
        "last_sent_at": hook.last_sent_at,
        "last_error": hook.last_error,
        "interval_seconds": discord_dashboard.INTERVAL_SECONDS,
    }


def _send_now(db: Session, hook: models.FacilityWebhook) -> dict:
    try:
        discord_dashboard.send(db, hook)
    except discord_dashboard.WebhookError:
        pass  # recorded in hook.last_error, shown by the page
    return _webhook_status(hook)


@router.get("/{facility_id}/discord-webhook")
def get_discord_webhook(facility_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    if not crud.get_facility(db, facility_id):
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    return _webhook_status(db.get(models.FacilityWebhook, facility_id))


@router.put("/{facility_id}/discord-webhook")
def put_discord_webhook(
    facility_id: int, data: WebhookIn, lang: str = "pt-BR", catalog_lang: str | None = None, db: Session = Depends(get_db)
):
    """Save the channel's webhook and post/edit the message right away. The
    message keeps the language the page had when it was saved."""
    if not crud.get_facility(db, facility_id):
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    url = data.url.strip()
    if not discord_dashboard.WEBHOOK_URL_RE.match(url):
        raise HTTPException(status_code=400, detail=err("invalid_webhook_url", lang))
    hook = db.get(models.FacilityWebhook, facility_id)
    if not hook:
        hook = models.FacilityWebhook(facility_id=facility_id, url=url)
        db.add(hook)
    elif hook.url != url:
        hook.url, hook.message_id = url, None  # another channel: start a new message there
    hook.lang, hook.catalog_lang = lang, catalog_lang or lang
    db.commit()
    return _send_now(db, hook)


@router.post("/{facility_id}/discord-webhook/send")
def send_discord_webhook(facility_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    hook = db.get(models.FacilityWebhook, facility_id)
    if not hook:
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    return _send_now(db, hook)


@router.delete("/{facility_id}/discord-webhook", status_code=204)
def delete_discord_webhook(facility_id: int, db: Session = Depends(get_db)):
    """Stops the updates and deletes the message from the channel (best
    effort — if Discord refuses, the message just stays, frozen)."""
    hook = db.get(models.FacilityWebhook, facility_id)
    if hook:
        discord_dashboard.delete_message(hook)
        db.delete(hook)
        db.commit()
