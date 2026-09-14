import json
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    icon: Mapped[str] = mapped_column(String(20), default="")
    target_max: Mapped[float | None] = mapped_column(default=None)
    farmable: Mapped[bool] = mapped_column(default=True)
    # Acquired from an outside source (a coalition/ally) instead of being
    # farmed or produced locally — e.g. a regiment that imports finished
    # Processed Construction Materials rather than making them itself. Takes
    # priority over `farmable` in the recommendation chain: an imported
    # resource is reported as "go get this from outside" regardless of
    # whether it's also technically gatherable or producible.
    imported: Mapped[bool] = mapped_column(default=False)
    resource_def_key: Mapped[str | None] = mapped_column(String(80), default=None)
    nickname: Mapped[str | None] = mapped_column(String(120), default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    @property
    def display_name(self) -> str:
        return self.nickname or self.name


class Facility(Base):
    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    buildings: Mapped[list["Building"]] = relationship(
        back_populates="facility", cascade="all, delete-orphan", order_by="Building.position"
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="facility", cascade="all, delete-orphan", order_by="Report.generated_at.desc()"
    )


class Building(Base):
    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(100), default="")
    position: Mapped[int] = mapped_column(default=0)
    building_type_key: Mapped[str | None] = mapped_column(String(80), default=None)
    # Up to the building type's queue_slots total, each running a different
    # recipe — the game allows distinct simultaneous production orders, not
    # just N copies of one recipe. JSON-encoded list of {recipe_key, queue_count}.
    # active_recipe_key/queue_count below are legacy (pre-multi-queue), kept only
    # so apply_migrations() can backfill existing single-recipe data once.
    production_slots_json: Mapped[str] = mapped_column("production_slots", Text, default="[]")
    active_recipe_key: Mapped[str | None] = mapped_column(String(80), default=None)
    queue_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    @property
    def production_slots(self) -> list[dict]:
        return json.loads(self.production_slots_json or "[]")

    @production_slots.setter
    def production_slots(self, slots: list[dict]) -> None:
        self.production_slots_json = json.dumps(slots)

    facility: Mapped["Facility"] = relationship(back_populates="buildings")
    stock_entries: Mapped[list["StockEntry"]] = relationship(
        back_populates="building", cascade="all, delete-orphan"
    )
    images: Mapped[list["UploadImage"]] = relationship(
        back_populates="building", cascade="all, delete-orphan"
    )


class StockEntry(Base):
    __tablename__ = "stock_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"))
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    quantity: Mapped[float] = mapped_column()
    # "normal" (crate/warehouse stock, unlimited — the default, used for every
    # resource) or "tank" (a liquid's 5000L building tank, capped). The same
    # liquid resource can have a current value in both at once — once the
    # tank is full, the game starts stacking the overflow as ordinary crates
    # instead. See memory/liquid_tank_system.md.
    storage: Mapped[str] = mapped_column(String(10), default="normal")
    source: Mapped[str] = mapped_column(String(20), default="manual")
    source_image_id: Mapped[int | None] = mapped_column(ForeignKey("upload_images.id"), default=None)
    recorded_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    building: Mapped["Building"] = relationship(back_populates="stock_entries")
    resource: Mapped["Resource"] = relationship()


class UploadImage(Base):
    __tablename__ = "upload_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"))
    file_path: Mapped[str] = mapped_column(String(500))
    uploaded_at: Mapped[datetime] = mapped_column(default=utcnow)

    building: Mapped["Building"] = relationship(back_populates="images")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    generated_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    markdown_content: Mapped[str] = mapped_column(Text)
    stock_snapshot: Mapped[str] = mapped_column(Text)
    # Paragraphs used to (re)build the Discord parts — kept separate from
    # markdown_content because the Discord version is a consolidated
    # facility-wide total, not the per-building breakdown shown in the
    # "Estoque Atual" block/tab. lang is stored too so history reopens the
    # "Parte X/Y" labels in whatever language the report was generated in.
    discord_content: Mapped[str] = mapped_column(Text, default="")
    lang: Mapped[str] = mapped_column(String(10), default="pt-BR")

    facility: Mapped["Facility"] = relationship(back_populates="reports")
