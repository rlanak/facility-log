from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db
from app.services import msupps, msupps_save
from app.services.errors_i18n import err

router = APIRouter(prefix="/api/tunnels", tags=["tunnels"])


def to_tunnel_out(tunnel: models.MaintenanceTunnel) -> schemas.TunnelOut:
    return schemas.TunnelOut(
        id=tunnel.id,
        key=tunnel.key,
        map_id=tunnel.map_id,
        hex_name=msupps_save.hex_display_name(tunnel.map_id),
        grid=tunnel.grid,
        label=tunnel.label,
        manual_rate_per_hour=tunnel.manual_rate_per_hour,
        facility_id=tunnel.facility_id,
        facility_name=tunnel.facility.name if tunnel.facility else None,
        pinned=tunnel.pinned,
        **msupps.tunnel_status(tunnel),
    )


@router.get("/status", response_model=schemas.TunnelStatusOut)
def tunnel_status():
    save = msupps_save.locate_save()
    return schemas.TunnelStatusOut(
        parser_available=msupps_save.locate_parser() is not None,
        save_path=str(save) if save else None,
    )


@router.post("/sync", response_model=schemas.TunnelSyncOut)
def sync_tunnels(lang: str = "pt-BR", db: Session = Depends(get_db)):
    try:
        locations = msupps_save.read_pinned_locations()
    except msupps_save.SaveReadError as exc:
        detail = err(exc.key, lang)
        if exc.detail:
            detail += f" ({exc.detail})"
        raise HTTPException(status_code=503, detail=detail)
    result = crud.sync_tunnels(db, msupps_save.maintenance_tunnels(locations))
    return schemas.TunnelSyncOut(**result, save_path=str(msupps_save.locate_save()))


@router.get("", response_model=list[schemas.TunnelOut])
def list_tunnels(facility_id: int | None = None, db: Session = Depends(get_db)):
    return [to_tunnel_out(t) for t in crud.get_tunnels(db, facility_id)]


@router.put("/{tunnel_id}", response_model=schemas.TunnelOut)
def update_tunnel(tunnel_id: int, data: schemas.TunnelUpdate, lang: str = "pt-BR", db: Session = Depends(get_db)):
    tunnel = crud.get_tunnel(db, tunnel_id)
    if not tunnel:
        raise HTTPException(status_code=404, detail=err("tunnel_not_found", lang))
    if data.facility_id is not None and not crud.get_facility(db, data.facility_id):
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    return to_tunnel_out(crud.update_tunnel(db, tunnel, data))


@router.delete("/{tunnel_id}", status_code=204)
def delete_tunnel(tunnel_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    tunnel = crud.get_tunnel(db, tunnel_id)
    if not tunnel:
        raise HTTPException(status_code=404, detail=err("tunnel_not_found", lang))
    crud.delete_tunnel(db, tunnel)
