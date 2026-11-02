from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.services import errors_i18n, foxhole_data
from app.services.number_parser import parse_quantity


def get_resources(db: Session) -> list[models.Resource]:
    return list(db.scalars(select(models.Resource).order_by(models.Resource.name)))


def get_resource(db: Session, resource_id: int) -> models.Resource | None:
    return db.get(models.Resource, resource_id)


def get_resource_by_name(db: Session, name: str) -> models.Resource | None:
    return db.scalar(select(models.Resource).where(func.lower(models.Resource.name) == name.lower()))


def create_resource(db: Session, data: schemas.ResourceCreate) -> models.Resource:
    resource = models.Resource(**data.model_dump())
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


def get_or_create_resource(db: Session, name: str, resource_def_key: str | None = None) -> models.Resource:
    # A catalog-linked resource is the same resource whatever name it was
    # saved under (e.g. the user created "Cmat" linked to construction
    # materials) — match on the link first so a save/OCR import doesn't
    # spawn a duplicate under the catalog's English name.
    if resource_def_key:
        linked = db.scalar(
            select(models.Resource).where(models.Resource.resource_def_key == resource_def_key).order_by(models.Resource.id)
        )
        if linked:
            return linked
    resource = get_resource_by_name(db, name)
    if resource:
        return resource
    farmable = True
    unlimited = False
    icon = ""
    if resource_def_key:
        res_def = foxhole_data.get_resource_def(resource_def_key)
        if res_def:
            farmable = res_def["farmable"]
            unlimited = res_def.get("unlimited", False)
    resource = models.Resource(
        name=name.strip(), resource_def_key=resource_def_key, farmable=farmable, unlimited=unlimited, icon=icon
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


def update_resource(db: Session, resource: models.Resource, data: schemas.ResourceUpdate) -> models.Resource:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(resource, field, value)
    db.commit()
    db.refresh(resource)
    return resource


ORIGIN_FLAGS = {
    "produced": {"farmable": False, "imported": False, "unlimited": False},
    "farmed": {"farmable": True, "imported": False, "unlimited": False},
    "imported": {"farmable": False, "imported": True, "unlimited": False},
    "unlimited": {"farmable": False, "imported": False, "unlimited": True},
}


def resources_for_facility(db: Session, facility_id: int) -> list[SimpleNamespace]:
    """Every resource as seen from one facility: same fields as the
    Resource rows, with farmable/imported/unlimited replaced by the
    facility's own origin where it set one (FacilityItemOrigin). Plain
    copies, not ORM rows — changing them never writes to the database."""
    origins = {
        o.resource_id: o.origin
        for o in db.scalars(select(models.FacilityItemOrigin).where(models.FacilityItemOrigin.facility_id == facility_id))
    }
    columns = [c.key for c in models.Resource.__table__.columns]
    result = []
    for r in get_resources(db):
        view = SimpleNamespace(**{c: getattr(r, c) for c in columns})
        if r.id in origins:
            view.__dict__.update(ORIGIN_FLAGS[origins[r.id]])
        result.append(view)
    return result


def set_item_origin(db: Session, facility_id: int, resource_id: int, origin: str) -> None:
    row = db.scalar(
        select(models.FacilityItemOrigin).where(
            models.FacilityItemOrigin.facility_id == facility_id, models.FacilityItemOrigin.resource_id == resource_id
        )
    )
    if row:
        row.origin = origin
    else:
        db.add(models.FacilityItemOrigin(facility_id=facility_id, resource_id=resource_id, origin=origin))
    db.commit()


def unlimited_resource_keys(resources) -> set[str]:
    """Catalog keys treated as always available in a facility (Resource.unlimited)
    — the player's own Resource row wins, else the catalog default (Water)."""
    by_key = {r.resource_def_key: r for r in resources if r.resource_def_key}
    keys = set()
    for key, res_def in foxhole_data.get_resource_defs().items():
        resource = by_key.get(key)
        if (resource.unlimited if resource else res_def.get("unlimited", False)):
            keys.add(key)
    return keys


def resolve_resource_name(resource: models.Resource, lang: str = "pt-BR") -> str:
    """A resource's stored `name` is the English catalog default baked in at
    import time (or a free-typed name for non-catalog resources) — resolve
    the localized catalog name instead when nothing custom overrides it.
    """
    if resource.nickname:
        return resource.nickname
    if resource.resource_def_key:
        return foxhole_data.resource_display_name(resource.resource_def_key, lang)
    return resource.name


def resolve_building_name(building: models.Building, lang: str = "pt-BR") -> str:
    if not building.building_type_key:
        return building.name
    building_type = foxhole_data.get_building_type(building.building_type_key)
    if not building_type or building.name != building_type["name_en"]:
        return building.name
    return foxhole_data.building_display_name(building.building_type_key, lang)


def resource_in_use(db: Session, resource_id: int) -> bool:
    return (
        db.scalar(
            select(models.StockEntry.id).where(models.StockEntry.resource_id == resource_id).limit(1)
        )
        is not None
    )


def delete_resource(db: Session, resource: models.Resource) -> None:
    db.delete(resource)
    db.commit()


def get_facilities(db: Session) -> list[models.Facility]:
    return list(db.scalars(select(models.Facility).order_by(models.Facility.name)))


def get_facility(db: Session, facility_id: int) -> models.Facility | None:
    return db.get(models.Facility, facility_id)


def create_facility(db: Session, data: schemas.FacilityCreate) -> models.Facility:
    facility = models.Facility(**data.model_dump())
    db.add(facility)
    db.commit()
    db.refresh(facility)
    return facility


def update_facility(db: Session, facility: models.Facility, data: schemas.FacilityUpdate) -> models.Facility:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(facility, field, value)
    db.commit()
    db.refresh(facility)
    return facility


def delete_facility(db: Session, facility: models.Facility) -> None:
    db.delete(facility)
    db.commit()


def get_buildings(db: Session, facility_id: int) -> list[models.Building]:
    return list(
        db.scalars(
            select(models.Building)
            .where(models.Building.facility_id == facility_id)
            .order_by(models.Building.position, models.Building.id)
        )
    )


def get_building(db: Session, building_id: int) -> models.Building | None:
    return db.get(models.Building, building_id)


def _default_building_name(building_type_key: str | None) -> str:
    building_type = building_type_key and foxhole_data.get_building_type(building_type_key)
    return building_type["name_en"] if building_type else "Prédio"


def create_building(db: Session, facility_id: int, data: schemas.BuildingCreate) -> models.Building:
    payload = data.model_dump()
    payload["name"] = payload["name"] or _default_building_name(payload.get("building_type_key"))
    building = models.Building(facility_id=facility_id, **payload)
    db.add(building)
    db.commit()
    db.refresh(building)
    return building


def update_building(db: Session, building: models.Building, data: schemas.BuildingUpdate) -> models.Building:
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "name" and not value:
            value = _default_building_name(building.building_type_key)
        if field == "location":
            value = (value or "").strip() or None
        setattr(building, field, value)
    db.commit()
    db.refresh(building)
    return building


def delete_building(db: Session, building: models.Building) -> None:
    db.delete(building)
    db.commit()


def update_building_production(
    db: Session, building: models.Building, data: schemas.BuildingProductionUpdate
) -> models.Building:
    building.production_slots = [
        {"recipe_key": slot.recipe_key, "queue_count": slot.queue_count} for slot in data.slots if slot.queue_count > 0
    ]
    db.commit()
    db.refresh(building)
    return building


def get_current_stock_for_building(db: Session, building_id: int) -> list[models.StockEntry]:
    # Grouped by (resource_id, storage), not just resource_id: a liquid can
    # have a current value in both its tank and its crate stock at once (see
    # StockEntry.storage), and each needs its own "latest entry" independent
    # of the other.
    latest_ids_subq = (
        select(
            models.StockEntry.resource_id,
            models.StockEntry.storage,
            func.max(models.StockEntry.id).label("max_id"),
        )
        .where(models.StockEntry.building_id == building_id)
        .group_by(models.StockEntry.resource_id, models.StockEntry.storage)
        .subquery()
    )
    entries = db.scalars(
        select(models.StockEntry).join(
            latest_ids_subq, models.StockEntry.id == latest_ids_subq.c.max_id
        )
    )
    # Defensive: resource_in_use() now blocks deleting a resource that still has
    # stock entries, but this filters out any pre-existing orphaned rows (e.g.
    # from before that check existed) instead of crashing every caller that
    # reads entry.resource.
    return [e for e in entries if e.resource is not None]


def get_facility_targets(db: Session, facility_id: int) -> dict[int, float]:
    """resource_id → Meta in this facility."""
    rows = db.scalars(select(models.FacilityTarget).where(models.FacilityTarget.facility_id == facility_id))
    return {t.resource_id: t.target_max for t in rows}


def set_facility_target(db: Session, facility_id: int, resource: models.Resource, target_max: float | None) -> None:
    target = db.scalar(
        select(models.FacilityTarget).where(
            models.FacilityTarget.facility_id == facility_id, models.FacilityTarget.resource_id == resource.id
        )
    )
    if not target_max or target_max <= 0:
        if target:
            db.delete(target)
    elif target:
        target.target_max = target_max
    else:
        db.add(models.FacilityTarget(facility_id=facility_id, resource_id=resource.id, target_max=target_max))
    db.commit()


def facility_stock_totals(db: Session, facility_id: int) -> tuple[dict[str, float], dict[int, float]]:
    """Current stock of the whole facility (every building, tank + crate),
    by catalog key and by resource id — what a Meta is compared against."""
    by_key: dict[str, float] = {}
    by_id: dict[int, float] = {}
    for entries in get_current_stock_for_facility(db, facility_id).values():
        for e in entries:
            by_id[e.resource_id] = by_id.get(e.resource_id, 0) + e.quantity
            if e.resource.resource_def_key:
                by_key[e.resource.resource_def_key] = by_key.get(e.resource.resource_def_key, 0) + e.quantity
    return by_key, by_id


def get_current_stock_for_facility(db: Session, facility_id: int) -> dict[models.Building, list[models.StockEntry]]:
    buildings = get_buildings(db, facility_id)
    return {building: get_current_stock_for_building(db, building.id) for building in buildings}


def get_current_stock_by_resource_def(db: Session, building_id: int) -> dict[str, float]:
    """Current stock per Foxhole resource key, for production math — tank and
    crate quantities of the same liquid are summed, since a recipe can draw
    on both (this app doesn't model the tank/crate distinction at the
    production-input level, just at the stock-keeping level)."""
    entries = get_current_stock_for_building(db, building_id)
    totals: dict[str, float] = {}
    for e in entries:
        if e.resource.resource_def_key:
            totals[e.resource.resource_def_key] = totals.get(e.resource.resource_def_key, 0) + e.quantity
    return totals


def delete_stock_entries(db: Session, building_id: int, resource_id: int, storage: str) -> int:
    """Removes every logged entry for one resource+storage in a building —
    not just the latest — so it drops out of "current stock" entirely
    instead of reverting to whatever was logged before. The append-only log
    is for tracking real changes over time, not for undoing a mistaken
    launch (wrong resource, test data, wrong building); this is the
    "I shouldn't have logged this at all" escape hatch. Returns how many
    rows were deleted (0 means nothing to remove)."""
    entries = list(
        db.scalars(
            select(models.StockEntry).where(
                models.StockEntry.building_id == building_id,
                models.StockEntry.resource_id == resource_id,
                models.StockEntry.storage == storage,
            )
        )
    )
    for entry in entries:
        db.delete(entry)
    db.commit()
    return len(entries)


def add_stock_entries(
    db: Session,
    building_id: int,
    entries: list[schemas.StockEntryIn],
    lang: str = "pt-BR",
    catalog_lang: str | None = None,
    created_by_id: int | None = None,
) -> list[models.StockEntry]:
    catalog_lang = catalog_lang or lang
    parsed = [(entry, parse_quantity(entry.quantity_raw)) for entry in entries]

    created: list[models.StockEntry] = []
    for entry, quantity in parsed:
        resource = get_or_create_resource(db, entry.resource_name, entry.resource_def_key)
        def_key = entry.resource_def_key or resource.resource_def_key
        # Cap only applies to the tank itself — crate/"normal" stock of the
        # same liquid has no limit, same as any other resource.
        max_units = foxhole_data.liquid_tank_max_units(def_key) if def_key and entry.storage == "tank" else None
        # Rounded to 2 decimals on both sides: the frontend's "5000L" ->
        # units conversion rounds to 2 decimals before submitting, which can
        # land a hair above the backend's full-precision max (e.g. 166.67 vs
        # 166.666...) and falsely trip this check for an exact full tank.
        if max_units is not None and round(quantity, 2) > round(max_units, 2):
            raise ValueError(
                errors_i18n.err("liquid_tank_exceeded", lang).format(
                    name=resolve_resource_name(resource, catalog_lang), max=round(max_units, 1)
                )
            )
        stock_entry = models.StockEntry(
            building_id=building_id,
            resource_id=resource.id,
            quantity=quantity,
            storage=entry.storage,
            source=entry.source,
            source_image_id=entry.source_image_id,
            created_by_id=created_by_id,
        )
        db.add(stock_entry)
        created.append(stock_entry)
    db.commit()
    for entry in created:
        db.refresh(entry)
    return created


def create_upload_image(db: Session, building_id: int, file_path: str) -> models.UploadImage:
    image = models.UploadImage(building_id=building_id, file_path=file_path)
    db.add(image)
    db.commit()
    db.refresh(image)
    return image


def get_upload_image(db: Session, image_id: int) -> models.UploadImage | None:
    return db.get(models.UploadImage, image_id)


def get_building_images(db: Session, building_id: int) -> list[models.UploadImage]:
    return list(
        db.scalars(
            select(models.UploadImage)
            .where(models.UploadImage.building_id == building_id)
            .order_by(models.UploadImage.uploaded_at.desc())
        )
    )


def create_report(
    db: Session,
    facility_id: int,
    markdown_content: str,
    stock_snapshot: str,
    discord_content: str = "",
    lang: str = "pt-BR",
    created_by_id: int | None = None,
) -> models.Report:
    report = models.Report(
        created_by_id=created_by_id,
        facility_id=facility_id,
        markdown_content=markdown_content,
        stock_snapshot=stock_snapshot,
        discord_content=discord_content,
        lang=lang,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_reports(db: Session, facility_id: int) -> list[models.Report]:
    return list(
        db.scalars(
            select(models.Report)
            .where(models.Report.facility_id == facility_id)
            .order_by(models.Report.generated_at.desc())
        )
    )


def get_report(db: Session, report_id: int) -> models.Report | None:
    return db.get(models.Report, report_id)


def delete_report(db: Session, report: models.Report) -> None:
    db.delete(report)
    db.commit()
