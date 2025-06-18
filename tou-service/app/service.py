import pytz
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from app.database.models import PricingPeriod, PricingPeriodStatus, Region, Charger, ChargerPriceStatus
from app.schemas.data_transfer_objects import DistancedChargerDTO, DistancedChargersDTO, PatchChargerDTO, PricingPeriodDTO, PricingPeriodsDTO, PricingScheduleDTO, RegionDTO, RegionsDTO, ChargersDTO, ChargerDTO, GeoJSONPoint
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from fastapi import HTTPException
from app.utils.time_utils import is_time_in_interval
from sqlalchemy.sql import func, text
from sqlalchemy import cast, MetaData
from geoalchemy2 import Geography
from app.database.database import Base, engine
from sqlalchemy_schemadisplay import create_schema_graph

def init_db_min(db: Session):
    region_alameda_ca = Region(
        name="Alameda County",
        state_code="CA",
        region_price_tier=4
    )
    region_contra_costa_ca = Region(
        name="Contra Costa County",
        state_code="CA",
        region_price_tier=4
    )
    region_az = Region(
        name="Maricopa County",
        state_code="AZ",
        region_price_tier=2
    )
    
    # db.add(region_ca)
    db.add_all([region_alameda_ca, region_contra_costa_ca, region_az])
    db.commit()
    
    charger = Charger(
        region_id=region_alameda_ca.id,
        # coordinates="POINT(37.79961142382174 -122.21741333895199)"
        location=from_shape(Point(-122.21741333895199, 37.79961142382174), srid=4326),
        time_zone="America/Los_Angeles",
        in_use=False,
        charger_price_tier=1,
        price_status=ChargerPriceStatus.UP_TO_DATE,
        operational=True
    )
    db.add(charger)
    db.commit()
    
def create_db_viz(db: Session):
    # Create a new MetaData object with only the tables you want
    metadata = MetaData()
    included_tables = ['regions', 'chargers', 'pricing_periods']

    # Bind only the desired tables
    for table_name in included_tables:
        table = Base.metadata.tables[table_name]
        table.tometadata(metadata)

    # Generate and export the diagram
    graph = create_schema_graph(
        engine,
        metadata=metadata,
                                show_datatypes=True,  # show column types
                                show_indexes=False,   # show index info
                                rankdir='LR',         # 'TB' or 'LR'
                                concentrate=False)

    graph.write_png("/data/filtered_schema.png")


def get_regions(
        db: Session,
        state_code: str,
        name_like: str) -> RegionsDTO:
    query = db.query(Region)
    
    if state_code:
        query = query.filter(func.lower(Region.state_code) == state_code.lower())
    if name_like:
        query = query.filter(func.lower(Region.name).like(f"%{name_like.lower()}%"))
    regions = query.all()
    
    result = RegionsDTO(
        self="/regions",
        count=len(regions),
        contents=[
            RegionDTO(
                self=f"/regions/{region.id}",
                id=str(region.id),
                name=region.name,
                state_code=region.state_code,
                region_price_tier=region.region_price_tier
            ) for region in regions
        ]
    )
    
    return result
    
def get_region(region_id: str, db: Session) -> RegionDTO | None:
    region = db.query(Region).filter(Region.id == region_id).first()
    
    if not region:
        return None
    
    result = RegionDTO(
        self=f"/regions/{region.id}",
        id=str(region.id),
        name=region.name,
        state_code=region.state_code,
        region_price_tier=region.region_price_tier
    )
    
    return result

def get_chargers(
        db: Session,
        operational_only: bool,
        not_in_use_only: bool,
        region_id: str) -> ChargersDTO:
    query = db.query(Charger)
    
    if not_in_use_only:
        query = query.filter(Charger.in_use == False)
    
    if operational_only:
        query = query.filter(Charger.operational == True)
        
    if region_id:
        query = query.filter(Charger.region_id == region_id)
        
    chargers = query.all()
    
    contents = []
    for charger in chargers:
        point = to_shape(charger.location)
        coords = (point.x, point.y)
        geo_point = GeoJSONPoint(
            type="Point",
            coordinates=coords
        )
        
        charger_dto = ChargerDTO(
            self=f"/chargers/{charger.id}",
            id=str(charger.id),
            region_id=str(charger.region_id),
            location=geo_point,
            time_zone=charger.time_zone,
            in_use=charger.in_use,
            charger_price_tier=charger.charger_price_tier,
            price_status=charger.price_status.value,
            operational=charger.operational
        )
        contents.append(charger_dto)
    
    result = ChargersDTO(
        self="/chargers",
        count=len(contents),
        contents=contents
    )
    
    return result

def get_charger(charger_id: str, db: Session) -> ChargerDTO | None:
    charger = db.query(Charger).filter(Charger.id == charger_id).first()
    
    if not charger:
        return None
        
    point = to_shape(charger.location)
    coords = (point.x, point.y)
    
    geo_point = GeoJSONPoint(
        type="Point",
        coordinates=coords
    )
    
    result = ChargerDTO(
        self=f"/chargers/{charger.id}",
        id=str(charger.id),
        region_id=str(charger.region_id),
        location=geo_point,
        time_zone=charger.time_zone,
        in_use=charger.in_use,
        charger_price_tier=charger.charger_price_tier,
        price_status=charger.price_status.value,
        operational=charger.operational
    )
    
    return result

def get_charger_pricing_schedule(charger_id: str, db: Session) -> list:
    # Explicitly eager-load pricing periods for this specific query
    charger = db.query(Charger).options(joinedload(Charger.pricing_periods)).filter(Charger.id == charger_id).first()
    
    if not charger:
        raise HTTPException(status_code=404, detail="Charger not found")

    if charger.price_status != ChargerPriceStatus.UP_TO_DATE:
        raise HTTPException(status_code=503, detail="Charger pricing schedule is undergoing maintenance")

    if charger.pricing_periods is None or len(charger.pricing_periods) == 0:
        raise HTTPException(status_code=404, detail="Charger pricing schedule not found")

    pricing_periods = sorted(charger.pricing_periods, key=lambda x: x.start_time)
    
    result = PricingScheduleDTO(
        self=f"/chargers/{charger.id}/pricing_schedule",
        count=len(pricing_periods),
        charger_id=str(charger.id),
        pricing_periods=[
            PricingPeriodDTO(
                self=f"/pricing_period/{period.id}",
                id=str(period.id),
                charger_id=str(charger.id),
                start_time=period.start_time,
                end_time=period.end_time,
                demand_index=period.demand_index,
                price_per_kwh=period.price_per_kwh,
                status=period.status.value
            ) for period in pricing_periods
        ]
    )
    
    return result

def get_charger_current_pricing_period(charger_id: str, db: Session) -> PricingPeriodDTO | None:
    # Explicitly eager-load pricing periods for this specific query
    charger = db.query(Charger).options(joinedload(Charger.pricing_periods)).filter(Charger.id == charger_id).first()
    charger_tz = pytz.timezone(charger.time_zone)
    current_time = datetime.now(charger_tz)

    if not charger:
        raise HTTPException(status_code=404, detail="Charger not found")
    
    candidate_period = None
    for period in charger.pricing_periods:
        if is_time_in_interval(current_time.time(), period.start_time, period.end_time):
            candidate_period = period
            if period.status == PricingPeriodStatus.UP_TO_DATE:
                break
    
    if candidate_period:     
        return PricingPeriodDTO(
            self=f"/pricing_period/{candidate_period.id}",
            id=str(candidate_period.id),
            charger_id=str(charger.id),
            start_time=candidate_period.start_time,
            end_time=candidate_period.end_time,
            demand_index=candidate_period.demand_index,
            price_per_kwh=candidate_period.price_per_kwh,
            status=candidate_period.status.value
        )

    raise HTTPException(status_code=404, detail="Current pricing period not found")

def get_pricing_period(pricing_period_id: str, db: Session) -> PricingPeriodDTO | None:
    pricing_period = db.query(PricingPeriod).filter(PricingPeriod.id == pricing_period_id).first()
    
    if not pricing_period:
        return None
    
    result = PricingPeriodDTO(
        self=f"/pricing_periods/{pricing_period.id}",
        id=str(pricing_period.id),
        charger_id=str(pricing_period.charger_id),
        start_time=pricing_period.start_time,
        end_time=pricing_period.end_time,
        demand_index=pricing_period.demand_index,
        price_per_kwh=pricing_period.price_per_kwh,
        status=pricing_period.status.value
    )
    
    return result

def get_nearest_chargers(
        db: Session,
        lat: float, 
        lon: float, 
        count: int,
        operational_only: bool = True,
        not_in_use_only: bool = False) -> ChargersDTO:
    """
    Find the nearest chargers to a given location.
    
    Args:
        lat: Latitude of the location
        lon: Longitude of the location
        count: Maximum number of chargers to return
        not_in_use_only: If True, only return chargers that are not in use
        db: Database session
        
    Returns:
        ChargersDTO: DTO containing the nearest chargers
    """
    point = Point(lon, lat)
    wkb_point = from_shape(point, srid=4326)
    
    query = db.query(
        Charger,
        func.ST_DistanceSphere(
            Charger.location,
            wkb_point
        ).label('distance')
    )
    
    if not_in_use_only:
        query = query.filter(Charger.in_use == False)
    
    if operational_only:
        query = query.filter(Charger.operational == True)
    
    chargers_with_distance = query.order_by('distance').limit(count).all()
    
    contents = []
    for charger, distance in chargers_with_distance:
        point = to_shape(charger.location)
        coords = (point.x, point.y)
        geo_point = GeoJSONPoint(
            type="Point",
            coordinates=coords
        )
        
        charger_dto = DistancedChargerDTO(
            self=f"/chargers/{charger.id}",
            id=str(charger.id),
            region_id=str(charger.region_id),
            location=geo_point,
            time_zone=charger.time_zone,
            in_use=charger.in_use,
            charger_price_tier=charger.charger_price_tier,
            price_status=charger.price_status.value,
            operational=charger.operational,
            distance_meters=round(distance, 2)
        )
        contents.append(charger_dto)
    
    result = DistancedChargersDTO(
        self=f"/chargers/nearest?lat={lat}&lon={lon}&count={count}&not_in_use_only={not_in_use_only}",
        count=len(contents),
        contents=contents
    )
    
    return result

def get_pricing_periods(db: Session, charger_id: str, status: PricingPeriodStatus):
    """
    Get all pricing periods for a charger.
    If status is provided, only return pricing periods with that status.
    """
    query = db.query(PricingPeriod).filter(PricingPeriod.charger_id == charger_id)
    
    if status:
        query = query.filter(PricingPeriod.status == status)
    
    pricing_periods = query.all()
    
    result = PricingPeriodsDTO(
        self=f"/chargers/{charger_id}/pricing_periods",
        count=len(pricing_periods),
        charger_id=str(charger_id),
        pricing_periods=[
            PricingPeriodDTO(
                self=f"/pricing_periods/{period.id}",
                id=str(period.id),
                charger_id=str(period.charger_id),
                start_time=period.start_time,
                end_time=period.end_time,
                demand_index=period.demand_index,
                price_per_kwh=period.price_per_kwh,
                status=period.status.value
            ) for period in pricing_periods
        ]
    )

    return result

def update_charger(charger_id: str, db: Session, charger_patch: PatchChargerDTO) -> ChargerDTO | None:
    """
    Update a charger's price status or price tier.
    """
    charger = db.query(Charger).filter(Charger.id == charger_id).first()
    
    if not charger:
        return None
    
    if charger_patch.price_status:
        charger.price_status = ChargerPriceStatus(charger_patch.price_status)
    
    if charger_patch.charger_price_tier:
        charger.charger_price_tier = charger_patch.charger_price_tier
    
    db.commit()
    
    point = to_shape(charger.location)
    coords = (point.x, point.y)
    geo_point = GeoJSONPoint(
        type="Point",
        coordinates=coords
    )
    
    result = ChargerDTO(
        self=f"/chargers/{charger.id}",
        id=str(charger.id),
        region_id=str(charger.region_id),
        location=geo_point,
        time_zone=charger.time_zone,
        in_use=charger.in_use,
        charger_price_tier=charger.charger_price_tier,
        price_status=charger.price_status.value,
        operational=charger.operational
    )
    
    return result

