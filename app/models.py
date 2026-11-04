import json
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.crypto import EncryptedText
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    icon: Mapped[str] = mapped_column(String(20), default="")
    # Legacy global Meta — moved to FacilityTarget (per facility) and
    # cleared by apply_migrations(); no longer read anywhere.
    target_max: Mapped[float | None] = mapped_column(default=None)
    farmable: Mapped[bool] = mapped_column(default=True)
    # Acquired from an outside source (a coalition/ally) instead of being
    # farmed or produced locally — e.g. a regiment that imports finished
    # Processed Construction Materials rather than making them itself. Takes
    # priority over `farmable` in the recommendation chain: an imported
    # resource is reported as "go get this from outside" regardless of
    # whether it's also technically gatherable or producible.
    imported: Mapped[bool] = mapped_column(default=False)
    # Abundant in the facility (e.g. Water: a couple of pump queues already
    # overfill it): treated as always available — never limits a production
    # estimate, never needs producing/farming in the Meta chain, and is left
    # out of the report's stock lists. Takes priority over farmable/imported.
    unlimited: Mapped[bool] = mapped_column(default=False)
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
    # Web mode only (see app/auth.py): who created it, and whether only that
    # person sees it. NULL owner = created in local mode or before this
    # existed: shared, and whoever marks it private becomes the owner.
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    private: Mapped[bool] = mapped_column(default=False)
    owner: Mapped["User | None"] = relationship()

    buildings: Mapped[list["Building"]] = relationship(
        back_populates="facility", cascade="all, delete-orphan", order_by="Building.position"
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="facility", cascade="all, delete-orphan", order_by="Report.generated_at.desc()"
    )
    targets: Mapped[list["FacilityTarget"]] = relationship(back_populates="facility", cascade="all, delete-orphan")
    item_origins: Mapped[list["FacilityItemOrigin"]] = relationship(cascade="all, delete-orphan")
    webhook: Mapped["FacilityWebhook | None"] = relationship(cascade="all, delete-orphan")

    @property
    def owner_name(self) -> str | None:
        return (self.owner.display_name or self.owner.username) if self.owner else None


class FacilityItemOrigin(Base):
    """Where an item comes from in one facility — "produced", "farmed",
    "imported" or "unlimited" (abundant). Overrides the resource's global
    flags (farmable/imported/unlimited), which stay as the default for
    facilities that never set it: one FAC may import Cmat while another
    makes it. See crud.resources_for_facility()."""

    __tablename__ = "facility_item_origins"
    __table_args__ = (UniqueConstraint("facility_id", "resource_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    origin: Mapped[str] = mapped_column(String(20))


class FacilityWebhook(Base):
    """Discord webhook that keeps one message in a channel showing the
    facility's "Ao vivo" estimate — see services/discord_dashboard.py. The
    URL works like a password (anyone with it can post there), so the API
    never sends it back whole. `message_id` is the message being edited;
    when it's gone (deleted in Discord) a new one is posted."""

    __tablename__ = "facility_webhooks"

    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), primary_key=True)
    url: Mapped[str] = mapped_column(EncryptedText)  # encrypted at rest (app/crypto.py)
    message_id: Mapped[str | None] = mapped_column(String(40), default=None)
    # Thread (tópico) inside the webhook's channel to post in; NULL = the channel itself.
    thread_id: Mapped[str | None] = mapped_column(String(40), default=None)
    lang: Mapped[str] = mapped_column(String(10), default="pt-BR")
    catalog_lang: Mapped[str] = mapped_column(String(10), default="pt-BR")
    last_sent_at: Mapped[datetime | None] = mapped_column(default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)


class FacilityTarget(Base):
    """Stock target (Meta) of one resource in one facility — the report works
    out what's missing down the production chain to reach it. Per facility
    (each FAC wants different amounts); replaced the old global
    `Resource.target_max`, which apply_migrations() copied into every
    facility once."""

    __tablename__ = "facility_targets"
    __table_args__ = (UniqueConstraint("facility_id", "resource_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    target_max: Mapped[float]

    facility: Mapped["Facility"] = relationship(back_populates="targets")
    resource: Mapped["Resource"] = relationship()


class Building(Base):
    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(100), default="")
    position: Mapped[int] = mapped_column(default=0)
    # The map pin (save_reader.pin_key) this building's stockpile is imported
    # from — remembered after the first "Importar do save" so the next import
    # preselects it.
    save_pin_key: Mapped[str | None] = mapped_column(String(160), default=None)
    building_type_key: Mapped[str | None] = mapped_column(String(80), default=None)
    # The upgrade module installed (a recipe "module" name from the catalog,
    # e.g. "Forge Upgrade"); None = base building. The game allows only one
    # per building, and it adds recipes on top of the base ones — the
    # production form only offers Base + this module's recipes.
    upgrade: Mapped[str | None] = mapped_column(String(80), default=None)
    # Free text naming where the building sits inside the facility (a
    # facility can span spots, e.g. MTSs in two places) — groups the cards.
    # Filled from the save pin's region + grid square on the first link if
    # still empty; the user can rename it.
    location: Mapped[str | None] = mapped_column(String(120), default=None)
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
    # Who logged it (web mode). NULL for local mode / entries from before login existed.
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)

    building: Mapped["Building"] = relationship(back_populates="stock_entries")
    resource: Mapped["Resource"] = relationship()
    created_by: Mapped["User | None"] = relationship()


class User(Base):
    """A Discord account that logged in (web mode only — see app/auth.py).
    Only id, name and avatar: no Discord token is kept."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    discord_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), default="")
    display_name: Mapped[str] = mapped_column(String(100), default="")
    avatar_url: Mapped[str | None] = mapped_column(String(300), default=None)
    # Unused since 03/11/2026 and always empty: no Discord token is kept
    # (app/auth.py). Columns left so old databases don't need a rebuild.
    access_token: Mapped[str] = mapped_column(EncryptedText, default="")
    refresh_token: Mapped[str] = mapped_column(EncryptedText, default="")
    token_expires_at: Mapped[int] = mapped_column(default=0)
    roles_checked_at: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_login_at: Mapped[datetime] = mapped_column(default=utcnow)

    @property
    def name(self) -> str:
        return self.display_name or self.username


class AppSetting(Base):
    """Plain key/value app settings (capture engine choice, Ollama/API
    config) — see services/capture. Server-wide, not per user."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(EncryptedText, default="")  # holds the API key: encrypted at rest


class CodenameAlias(Base):
    """User-picked catalog resource for a game item codename the catalog
    doesn't map yet (resources.json "codename"), so a save import only asks
    about it once."""

    __tablename__ = "codename_aliases"

    codename: Mapped[str] = mapped_column(String(120), primary_key=True)
    resource_def_key: Mapped[str] = mapped_column(String(80))


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
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)

    facility: Mapped["Facility"] = relationship(back_populates="reports")
    created_by: Mapped["User | None"] = relationship()
