from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import auth, crud, models, schemas
from app.database import get_db
from app.services import foxhole_data, save_reader
from app.services.errors_i18n import err

router = APIRouter(tags=["save"])


def _local_save_allowed(request: Request) -> bool:
    # In web mode the "local" save is the *server's* — only offer it to a
    # browser on the server machine itself, never to remote users.
    return not auth.config.enabled or auth.is_local_request(request)


@router.get("/api/save/status", response_model=schemas.SaveStatusOut)
def save_status(request: Request):
    save = save_reader.locate_save() if _local_save_allowed(request) else None
    return schemas.SaveStatusOut(
        parser_available=save_reader.locate_parser() is not None,
        local_save=str(save) if save else None,
    )


@router.post("/api/save/pins", response_model=list[schemas.SavePinOut])
async def list_save_pins(
    request: Request,
    file: UploadFile | None = File(default=None),
    lang: str = "pt-BR",
    catalog_lang: str | None = None,
    db: Session = Depends(get_db),
):
    """Pinned map locations that have a cached stockpile, items already
    mapped to catalog resources where possible. Parses the uploaded .sav
    when one is sent (web mode), otherwise this PC's own save. Nothing is
    stored here — the user confirms each value before it's logged."""
    catalog_lang = catalog_lang or lang
    try:
        save_bytes = await file.read() if file else None
        if save_bytes is None and not _local_save_allowed(request):
            raise save_reader.SaveReadError("save_missing")
        locations = save_reader.read_pinned_locations(save_bytes)
    except save_reader.SaveReadError as exc:
        detail = err(exc.key, lang)
        if exc.detail:
            detail += f" ({exc.detail})"
        raise HTTPException(status_code=422, detail=detail)

    by_codename = dict(foxhole_data.resource_keys_by_codename())
    for alias in db.scalars(select(models.CodenameAlias)):
        by_codename.setdefault(alias.codename, alias.resource_def_key)
    building_types = foxhole_data.building_type_keys_by_codename()

    pins = []
    for loc in locations:
        if not loc.get("stockpile"):
            continue
        bt_key = building_types.get(loc["code_name"])
        kind = foxhole_data.building_display_name(bt_key, catalog_lang) if bt_key else loc["code_name"]
        items = []
        for item in loc["stockpile"]:
            def_key = by_codename.get(item["code_name"])
            items.append(
                schemas.SavePinItem(
                    codename=item["code_name"],
                    quantity=item["quantity"],
                    resource_def_key=def_key,
                    name=foxhole_data.resource_display_name(def_key, catalog_lang) if def_key else None,
                )
            )
        pins.append(
            schemas.SavePinOut(
                key=save_reader.pin_key(loc),
                code_name=loc["code_name"],
                building_type_key=bt_key,
                label=f"{kind} — {save_reader.hex_display_name(loc['map_id'])} {loc.get('grid_coordinate', '')}".strip(),
                location=f"{save_reader.hex_display_name(loc['map_id'])} {loc.get('grid_coordinate', '')}".strip(),
                last_updated_unix=loc["last_updated_unix"],
                items=items,
            )
        )
    # Most recently refreshed first: that's almost always the one just looked at.
    pins.sort(key=lambda p: -p.last_updated_unix)
    return pins


@router.put("/api/buildings/{building_id}/save-pin", response_model=schemas.BuildingOut)
def link_save_pin(building_id: int, data: schemas.SavePinLink, lang: str = "pt-BR", db: Session = Depends(get_db)):
    building = crud.get_building(db, building_id)
    if not building:
        raise HTTPException(status_code=404, detail=err("building_not_found", lang))
    building.save_pin_key = data.pin_key
    if data.location and not (building.location or "").strip():
        building.location = data.location.strip()
    db.commit()
    db.refresh(building)
    return building


@router.put("/api/save/aliases", status_code=204)
def set_codename_alias(data: schemas.CodenameAliasIn, lang: str = "pt-BR", db: Session = Depends(get_db)):
    if not foxhole_data.get_resource_def(data.resource_def_key):
        raise HTTPException(status_code=404, detail=err("resource_not_found", lang))
    alias = db.get(models.CodenameAlias, data.codename)
    if alias:
        alias.resource_def_key = data.resource_def_key
    else:
        db.add(models.CodenameAlias(codename=data.codename, resource_def_key=data.resource_def_key))
    db.commit()
