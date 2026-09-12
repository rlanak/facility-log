from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.services import foxhole_data
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
    resource = get_resource_by_name(db, name)
    if resource:
        return resource
    farmable = True
    icon = ""
    if resource_def_key:
        res_def = foxhole_data.get_resource_def(resource_def_key)
        if res_def:
            farmable = res_def["farmable"]
    resource = models.Resource(name=name.strip(), resource_def_key=resource_def_key, farmable=farmable, icon=icon)
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
    building.active_recipe_key = data.recipe_key
    building.queue_count = data.queue_count if data.recipe_key else 0
    db.commit()
    db.refresh(building)
    return building


def get_current_stock_for_building(db: Session, building_id: int) -> list[models.StockEntry]:
    latest_ids_subq = (
        select(
            models.StockEntry.resource_id,
            func.max(models.StockEntry.id).label("max_id"),
        )
        .where(models.StockEntry.building_id == building_id)
        .group_by(models.StockEntry.resource_id)
        .subquery()
    )
    return list(
        db.scalars(
            select(models.StockEntry).join(
                latest_ids_subq, models.StockEntry.id == latest_ids_subq.c.max_id
            )
        )
    )


def get_current_stock_for_facility(db: Session, facility_id: int) -> dict[models.Building, list[models.StockEntry]]:
    buildings = get_buildings(db, facility_id)
    return {building: get_current_stock_for_building(db, building.id) for building in buildings}


def add_stock_entries(
    db: Session, building_id: int, entries: list[schemas.StockEntryIn]
) -> list[models.StockEntry]:
    parsed = [(entry, parse_quantity(entry.quantity_raw)) for entry in entries]

    created: list[models.StockEntry] = []
    for entry, quantity in parsed:
        resource = get_or_create_resource(db, entry.resource_name, entry.resource_def_key)
        stock_entry = models.StockEntry(
            building_id=building_id,
            resource_id=resource.id,
            quantity=quantity,
            source=entry.source,
            source_image_id=entry.source_image_id,
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


def create_report(db: Session, facility_id: int, markdown_content: str, stock_snapshot: str) -> models.Report:
    report = models.Report(
        facility_id=facility_id, markdown_content=markdown_content, stock_snapshot=stock_snapshot
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
