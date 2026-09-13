from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResourceBase(BaseModel):
    name: str
    icon: str = ""
    target_max: float | None = None
    farmable: bool = True
    resource_def_key: str | None = None
    nickname: str | None = None


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    target_max: float | None = None
    farmable: bool | None = None
    nickname: str | None = None


class ResourceOut(ResourceBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class FacilityBase(BaseModel):
    name: str


class FacilityCreate(FacilityBase):
    pass


class FacilityUpdate(BaseModel):
    name: str | None = None


class FacilityOut(FacilityBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class BuildingBase(BaseModel):
    name: str | None = None
    role: str = ""
    position: int = 0
    building_type_key: str | None = None


class BuildingCreate(BuildingBase):
    pass


class BuildingUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    position: int | None = None


class BuildingOut(BuildingBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    facility_id: int
    active_recipe_key: str | None = None
    queue_count: int = 0


class BuildingProductionUpdate(BaseModel):
    recipe_key: str | None = None
    queue_count: int = 0


class ProductionEstimateItem(BaseModel):
    resource: str
    name: str
    qty: float


class ProductionEstimateOut(BaseModel):
    recipe_key: str
    module: str | None = None
    queue_count: int
    cycles: int
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


class StockEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    resource_id: int
    resource_name: str
    resource_icon: str
    quantity: float
    source: str
    recorded_at: datetime


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
