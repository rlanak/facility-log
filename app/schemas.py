from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResourceBase(BaseModel):
    name: str
    icon: str = ""
    target_max: float | None = None


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    target_max: float | None = None


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
    name: str
    role: str = ""
    position: int = 0


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


class StockEntryIn(BaseModel):
    resource_name: str
    quantity_raw: str


class StockEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    resource_id: int
    resource_name: str
    resource_icon: str
    quantity: float
    source: str
    recorded_at: datetime


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
