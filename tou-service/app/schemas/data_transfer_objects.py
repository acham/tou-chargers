from pydantic import BaseModel, field_serializer, Field
from datetime import time
from typing import Annotated
from app.database.models import ChargerPriceStatus, PricingPeriodStatus

class RegionDTO(BaseModel):
    self: Annotated[str, Field(description="Relative URL to the region resource")]
    kind: str = "Region"
    id: Annotated[str, Field(description="UUID of the region")]
    name: Annotated[str, Field(description="Name of the region")]
    state_code: Annotated[str, Field(description="State code of the region")]
    region_price_tier: Annotated[int, Field(description="Price tier of the region, integer from 1 to 5")]

class RegionsDTO(BaseModel):
    self: Annotated[str, Field(description="Relative URL to this collection of regions")]
    kind: str = "Collection"
    count: Annotated[int, Field(description="Number of regions in this collection")]
    contents: Annotated[list[RegionDTO], Field(description="List of regions in this collection")]

class GeoJSONPoint(BaseModel):
    type: str = "Point"
    coordinates: Annotated[tuple[float, float], Field(description="Coordinates of the point in (longitude, latitude) format")]
    
class ChargerDTO(BaseModel):
    self: Annotated[str, Field(description="Relative URL to the charger resource")]
    kind: str = "Charger"
    id: Annotated[str, Field(description="UUID of the charger")]
    region_id: Annotated[str, Field(description="UUID of the region this charger belongs to")]
    location: Annotated[GeoJSONPoint, Field(description="Location of the charger in GeoJSON format")]
    time_zone: Annotated[str, Field(description="Time zone of the charger")]
    in_use: Annotated[bool, Field(description="True if the charger is currently in use")]
    charger_price_tier: Annotated[int, Field(description="Price tier of the charger, integer from 1 to 5")]
    price_status: Annotated[ChargerPriceStatus, Field(description="Price status of the charger")]
    operational: Annotated[bool, Field(description="True if the charger is operational")]
    
class ChargersDTO(BaseModel):
    self: Annotated[str, Field(description="Relative URL to this collection of chargers")]
    kind: str = "Collection"
    count: Annotated[int, Field(description="Number of chargers in this collection")]
    contents: Annotated[list[ChargerDTO], Field(description="List of chargers in this collection")]
    
class DistancedChargerDTO(ChargerDTO):
    distance_meters: Annotated[float, Field(description="Distance from the specified location in meters")]
    
class DistancedChargersDTO(BaseModel):
    self: Annotated[str, Field(description="Relative URL to this collection of distanced chargers")]
    kind: str = "Collection"
    count: Annotated[int, Field(description="Number of distanced chargers in this collection")]
    contents: Annotated[list[DistancedChargerDTO], Field(description="List of distanced chargers in this collection")]
    
class PricingPeriodDTO(BaseModel):
    self: Annotated[str, Field(description="Relative URL to the pricing period resource")]
    kind: str = "PricingPeriod"
    id: Annotated[str, Field(description="UUID of the pricing period")]
    charger_id: Annotated[str, Field(description="UUID of the charger this pricing period belongs to")]
    start_time: Annotated[time, Field(description="Start time of the pricing period in HH:MM format")]
    end_time: Annotated[time, Field(description="End time of the pricing period in HH:MM format")]
    demand_index: Annotated[int, Field(description="Demand index of this pricing period, integer from 1 to 5")]
    price_per_kwh: Annotated[float, Field(description="Price per kWh for this pricing period")]
    status: Annotated[PricingPeriodStatus, Field(description="Status of the pricing period")]
    
    @field_serializer('start_time', 'end_time')
    def serialize_time(self, time_obj: time) -> str:
        return time_obj.isoformat()

class PricingScheduleDTO(BaseModel):
    self: Annotated[str, Field(description="Relative URL to this collection of pricing periods")]
    kind: str = "Collection"
    count: Annotated[int, Field(description="Number of pricing periods in this collection")]
    charger_id: Annotated[str, Field(description="UUID of the charger this pricing schedule belongs to")]
    pricing_periods: Annotated[list[PricingPeriodDTO], Field(description="List of pricing periods in this collection")]
    
class PricingPeriodsDTO(PricingScheduleDTO):
    pass

class PatchChargerDTO(BaseModel):
    price_status: Annotated[str | None,  Field(description="New price status")] = None  # Enum type
    charger_price_tier: Annotated[int | None, Field(description="New price tier, integer from 1 to 5")] = None

class UpdatePricingPeriodDTO(BaseModel):
    start_time: Annotated[str, Field(description="Start time in HH:MM format")]
    end_time: Annotated[str, Field(description="End time in HH:MM format")]
    demand_index: Annotated[int, Field(description="Demand index, integer from 1 to 5")]
    price_per_kwh: Annotated[float, Field(description="Price per kWh")]
    status: Annotated[PricingPeriodStatus, Field(description="Status of the pricing period")]  # Enum type

class CreatePricingPeriodDTO(BaseModel):
    start_time: Annotated[str, Field(description="Start time in HH:MM format")]
    end_time: Annotated[str, Field(description="End time in HH:MM format")]
    demand_index: Annotated[int, Field(description="Demand index, integer from 1 to 5")]
    price_per_kwh: Annotated[float, Field(description="Price per kWh")]
    status: Annotated[str, Field(description="Status of the pricing period")]  # Enum type

class CreatePricingPeriodsDTO(BaseModel):
    charger_id: Annotated[str, Field(description="UUID of the charger")]
    pricing_periods: Annotated[list[CreatePricingPeriodDTO], Field(description="List of pricing periods to be created")]
    
    @field_serializer('pricing_periods')
    def serialize_pricing_periods(self, periods: list[CreatePricingPeriodDTO]) -> list[dict]:
        return [period.model_dump() for period in periods]
    
class DeletePricingPeriodsDTO(BaseModel):
    pricing_period_ids: Annotated[list[str], Field(description="List of UUIDs of the pricing periods to be deleted")]

class DeletePricingPeriodsSuccessDTO(BaseModel):
    pricing_period_ids: Annotated[list[str], Field(description="List of UUIDs of the pricing periods that have been deleted")]

