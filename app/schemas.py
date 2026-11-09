from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ResourceBase(BaseModel):
    name: str
    icon: str = ""
    target_max: float | None = None
    farmable: bool = True
    imported: bool = False
    unlimited: bool = False
    resource_def_key: str | None = None
    nickname: str | None = None


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    target_max: float | None = None
    farmable: bool | None = None
    imported: bool | None = None
    unlimited: bool | None = None
    nickname: str | None = None


class ResourceOut(ResourceBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ItemOriginSet(BaseModel):
    resource_id: int
    origin: Literal["produced", "farmed", "imported", "unlimited"]


class TargetSet(BaseModel):
    # An existing resource, or a catalog item (created on first use).
    resource_id: int | None = None
    resource_def_key: str | None = None
    # None/0 removes the target.
    target_max: float | None = None


class TargetOut(BaseModel):
    resource: ResourceOut
    target_max: float
    current: float


class FacilityBase(BaseModel):
    name: str


class FacilityCreate(FacilityBase):
    pass


class FacilityUpdate(BaseModel):
    name: str | None = None
    private: bool | None = None  # web mode, owner only


class FacilityOut(FacilityBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
    owner_id: int | None = None
    owner_name: str | None = None
    private: bool = False


class BuildingBase(BaseModel):
    name: str | None = None
    role: str = ""
    position: int = 0
    building_type_key: str | None = None
    upgrade: str | None = None
    location: str | None = None


class BuildingCreate(BuildingBase):
    pass


class BuildingUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    position: int | None = None
    upgrade: str | None = None
    location: str | None = None


class ProductionSlot(BaseModel):
    recipe_key: str
    queue_count: int = 1


class BuildingOut(BuildingBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    facility_id: int
    save_pin_key: str | None = None
    production_slots: list[ProductionSlot] = []


class BuildingProductionUpdate(BaseModel):
    slots: list[ProductionSlot]


class PrivateOrderIn(BaseModel):
    owner_name: str = ""
    recipe_key: str
    # Loaded inputs as the game shows them, {resource_key: qty}.
    inputs: dict[str, float] = {}
    cycle_left_seconds: int = 0
    # None = now. Sent as UTC ISO by the browser.
    started_at: datetime | None = None


class ProductionEstimateItem(BaseModel):
    resource: str
    name: str
    qty: float
    available: float | None = None


class ProductionEstimateOut(BaseModel):
    recipe_key: str
    module: str | None = None
    queue_count: int
    cycles: int
    rounds: int
    cycle_seconds: int
    time_seconds: int
    eta: datetime
    outputs: list[ProductionEstimateItem]
    inputs_consumed: list[ProductionEstimateItem]
    inputs_per_cycle: list[ProductionEstimateItem]
    leftovers: list[ProductionEstimateItem]




class StockEntryIn(BaseModel):
    resource_name: str
    quantity_raw: str
    source: str = "manual"
    source_image_id: int | None = None
    resource_def_key: str | None = None
    storage: str = "normal"


class StockEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    resource_id: int
    resource_name: str
    resource_icon: str
    quantity: float
    storage: str
    source: str
    recorded_at: datetime
    created_by_name: str | None = None


class UploadImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    building_id: int
    url: str
    uploaded_at: datetime


class OcrCropRequest(BaseModel):
    x: int
    y: int
    width: int
    height: int


class OcrResult(BaseModel):
    available: bool
    raw_text: str
    guess: str


class DetectedStockItem(BaseModel):
    # None = a slot with a quantity whose item wasn't recognized (the user
    # picks it; see icon_match_service grid fallback).
    resource_def_key: str | None
    name_en: str | None
    name_pt: str | None = None
    confidence: float
    ambiguous: bool = False
    rival_key: str | None = None
    rival_name_en: str | None = None
    quantity_raw: str
    quantity_guess: str
    box_x: int
    box_y: int
    box_width: int
    box_height: int
    # Where the quantity sits (full screenshot pixels) — lets the browser read
    # it with the user's own AI when the server didn't (detect with read=false).
    number_x: int = 0
    number_y: int = 0
    number_width: int = 0
    number_height: int = 0


class StockpileDetectionOut(BaseModel):
    available: bool
    items: list[DetectedStockItem] = []


class BuildingStockOut(BaseModel):
    building: BuildingOut
    entries: list[StockEntryOut]


class ReportBlocks(BaseModel):
    header: str
    stock: str
    recommendation: str


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    facility_id: int
    generated_at: datetime
    markdown_content: str
    blocks: ReportBlocks
    parts: list[str]
    created_by_name: str | None = None


class SaveStatusOut(BaseModel):
    parser_available: bool
    local_save: str | None


class SavePinItem(BaseModel):
    codename: str
    quantity: int
    resource_def_key: str | None
    name: str | None


class SavePinOut(BaseModel):
    key: str
    code_name: str
    building_type_key: str | None
    label: str
    # Region + grid square ("Westgate G5"), used as the building's
    # location when it has none yet.
    location: str = ""
    last_updated_unix: int
    items: list[SavePinItem]


class SavePinLink(BaseModel):
    pin_key: str | None
    location: str | None = None


class CodenameAliasIn(BaseModel):
    codename: str
    resource_def_key: str


class CaptureProviderStatus(BaseModel):
    available: bool
    detail: str


class CaptureSettingsIn(BaseModel):
    capture_provider: str | None = None
    ollama_url: str | None = None
    ollama_model: str | None = None
    api_kind: str | None = None
    api_base_url: str | None = None
    api_model: str | None = None
    api_key: str | None = None
    clear_api_key: bool = False


class CaptureSettingsOut(BaseModel):
    capture_provider: str
    ollama_url: str
    ollama_model: str
    api_kind: str
    api_base_url: str
    api_model: str
    api_key_set: bool
    api_key_hint: str
    providers: dict[str, CaptureProviderStatus]
    ollama_vision_models: list[str]
    # False on a web server: its Ollama option is hidden and each user can
    # read with the AI on their own PC instead (in the browser).
    server_local_ai: bool = True


class UserOut(BaseModel):
    id: int
    name: str
    avatar_url: str | None


class MeOut(BaseModel):
    auth_enabled: bool
    user: UserOut | None


class IconExemplarIn(BaseModel):
    resource_def_key: str
    box_x: int
    box_y: int
    box_width: int
    box_height: int
