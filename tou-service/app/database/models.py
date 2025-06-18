import uuid
from datetime import datetime, time
from typing import Annotated
import enum

from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point

from .database import Base

class ChargerPriceStatus(enum.Enum):
    UP_TO_DATE = "up_to_date"
    PENDING = "pending"

class PricingPeriodStatus(enum.Enum):
    UP_TO_DATE = "up_to_date"
    STALE = "stale"

class Region(Base):
    __tablename__ = "regions"

    id: Mapped[Annotated[uuid.UUID, mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )]]
    
    name: Mapped[str] = mapped_column(nullable=False)
    state_code: Mapped[str] = mapped_column(nullable=False)
    # 1 to 5
    region_price_tier: Mapped[int] = mapped_column(nullable=False)

class Charger(Base):
    __tablename__ = "chargers"

    id: Mapped[Annotated[uuid.UUID, mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )]]
    
    region_id: Mapped[Annotated[uuid.UUID, mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regions.id"),
        nullable=False
    )]]
    location: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=False
    )
    time_zone: Mapped[str] = mapped_column(nullable=False)
    in_use: Mapped[bool] = mapped_column(nullable=False)
    # 1 to 5
    charger_price_tier: Mapped[int] = mapped_column(nullable=False)
    price_status: Mapped[ChargerPriceStatus] = mapped_column(Enum(ChargerPriceStatus), nullable=False)
    operational: Mapped[bool] = mapped_column(nullable=False)

    pricing_periods: Mapped[list["PricingPeriod"]] = relationship("PricingPeriod", back_populates="charger")
    
    def set_location(self, lat: float, lon: float):
        self.location = from_shape(Point(lon, lat), srid=4326)

    def get_location(self) -> tuple[float, float]:
        point = to_shape(self.location)
        coords = (point.y, point.x)
        return coords
    
class PricingPeriod(Base):
    __tablename__ = "pricing_periods"

    id: Mapped[Annotated[uuid.UUID, mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )]]
    charger_id: Mapped[Annotated[uuid.UUID, mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chargers.id"),
        nullable=False
    )]]
    start_time: Mapped[time] = mapped_column(nullable=False)
    end_time: Mapped[time] = mapped_column(nullable=False)
    # 1 to 5
    demand_index: Mapped[int] = mapped_column(nullable=False)
    price_per_kwh: Mapped[float] = mapped_column(nullable=False)
    status: Mapped[PricingPeriodStatus] = mapped_column(Enum(PricingPeriodStatus), nullable=False)
    
    # Relationship back to the charger
    charger: Mapped["Charger"] = relationship("Charger", back_populates="pricing_periods")
