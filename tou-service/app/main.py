from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point, mapping

from app.database.database import get_db, engine, Base
from app.database.models import PricingPeriodStatus, Region, Charger, ChargerPriceStatus
from app.schemas.data_transfer_objects import CreatePricingPeriodsDTO, DeletePricingPeriodsDTO, PatchChargerDTO, PricingPeriodDTO, PricingPeriodsDTO, PricingScheduleDTO, RegionDTO, RegionsDTO, ChargersDTO, ChargerDTO, UpdatePricingPeriodDTO
import app.service as service
import app.data_gen as data_gen

# Create database tables
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

fast_app = FastAPI(root_path="/tou-service")

@fast_app.get("/")
async def root():
    return {"message": "tou-service is running!"}

@fast_app.get("/db-test", tags=["Development"])
async def test_db(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"message": "Database connection successful!"}
    except Exception as e:
        return {"message": "Database connection failed", "error": str(e)}

@fast_app.post("/init-db-min", tags=["Development"])
async def init_db_min(db: Session = Depends(get_db)):
    service.init_db_min(db)
    return {"message": "Database initialized with dev data!"}

@fast_app.post("/create-schema-viz", tags=["Development"])
async def create_schema_viz(db: Session = Depends(get_db)):
    service.create_db_viz(db)
    return {"message": "Database schema visualization created!"}

@fast_app.post("/init-db-dev", tags=["Development"])
async def init_db_dev(db: Session = Depends(get_db)):
    """
    Initialize the database with development data.
    Creates regions for Alameda County and Contra Costa County, CA, 
    for and chargers in the Alameda and Contra Costa counties.
    """
    data_gen.generate_data_for_alameda_contra_costa(db)
    return {"message": "Database initialized with dev data!"}
    
@fast_app.get("/regions", tags=["Customer"])
async def get_regions(
        state_code: str = Query(
            default=None,
            description="If provided, only return regions with this state code, case insensitive."),
        name_like: str = Query(
            default=None,
            description="If provided, only return regions with names containing this string (case insensitive)."),
        db: Session = Depends(get_db)) -> RegionsDTO:
    result = service.get_regions(db, state_code, name_like)
    
    return result

@fast_app.get("/regions/{region_id}", tags=["Customer"])
async def get_region(region_id: str, db: Session = Depends(get_db)) -> RegionDTO:
    result = service.get_region(region_id, db)
    
    if not result:
        raise HTTPException(status_code=404, detail="Region not found")
    
    return result

@fast_app.get("/chargers", tags=["Customer"])
async def get_chargers(
    operational_only: bool = Query(
        default=False,
        description="If True, only return operational chargers."),
    not_in_use_only: bool = Query(
        default=False,
        description="If True, only return chargers that are currently not in use."),
    region_id: str = Query(
        default=None,
        description="If provided, only return chargers in this region."),
    db: Session = Depends(get_db)) -> ChargersDTO:
    """
    Get all chargers.
    """
    result = service.get_chargers(
        db,
        operational_only=operational_only,
        not_in_use_only=not_in_use_only,
        region_id=region_id
    )
    
    return result

@fast_app.get("/chargers/{charger_id}", tags=["Customer"])
async def get_charger(charger_id: str, db: Session = Depends(get_db)) -> ChargerDTO:
    result = service.get_charger(charger_id, db)
    
    if not result:
        raise HTTPException(status_code=404, detail="Charger not found")
    
    return result

@fast_app.get("/chargers/{charger_id}/pricing-schedule", tags=["Customer"])
async def get_charger_pricing_schedule(charger_id: str, db: Session = Depends(get_db)) -> PricingScheduleDTO:
    result = service.get_charger_pricing_schedule(charger_id, db)
    
    if not result:
        raise HTTPException(status_code=404, detail="Charger not found")
    
    return result

@fast_app.get("/chargers/{charger_id}/current-pricing-period", tags=["Customer"])
async def get_charger_current_pricing_period(charger_id: str, db: Session = Depends(get_db)) -> PricingPeriodDTO:
    """
    Get the current pricing period for a charger.
    
    If the charger is operational, there should always be a current pricing period, even if
    it is marked as STALE.
    This endpoint assumes the requester is in the same time zone as the charger.
    """
    result = service.get_charger_current_pricing_period(charger_id, db)
    
    if not result:
        raise HTTPException(status_code=404, detail="Charger not found")
    
    return result

@fast_app.get("/pricing-periods/{pricing_period_id}", tags=["Customer"])
async def get_pricing_period(pricing_period_id: str, db: Session = Depends(get_db)) -> PricingPeriodDTO:
    result = service.get_pricing_period(pricing_period_id, db)
    
    if not result:
        raise HTTPException(status_code=404, detail="Pricing period not found")
    
    return result

@fast_app.get("/nearest-chargers", tags=["Customer"])
async def get_nearest_chargers(
    lat: float = Query(..., description="Latitude of the location"),    
    lon: float = Query(..., description="Longitude of the location"),
    count: int = Query(..., description="Number of nearest chargers to return"),
    operational_only: bool = Query(default=True, description="If True, only return operational chargers."), 
    not_in_use_only: bool = Query(default=False, description="If True, only return chargers that are currently not in use."),
    db: Session = Depends(get_db)
) -> ChargersDTO:
    """
    Get the nearest chargers within a specified distance.
    """
    result = service.get_nearest_chargers(
        db,
        lat, lon, count, 
        operational_only, not_in_use_only)
    
    return result

@fast_app.get("/chargers/{charger_id}/pricing-periods", tags=["Price setting"])
async def get_pricing_periods(
    charger_id: str,
    status: PricingPeriodStatus = Query(default=None, description="Filter by status"),
    db: Session = Depends(get_db)
) -> PricingPeriodsDTO:
    """
    Get all pricing periods for a charger.
    If status is provided, only return pricing periods with that status.
    """
    pricing_periods = service.get_pricing_periods(db, charger_id, status)
    
    return pricing_periods

@fast_app.patch("/chargers/{charger_id}", tags=["Price setting"])
async def update_charger(
    charger_id: str,
    charger_patch: PatchChargerDTO,
    db: Session = Depends(get_db)
) -> ChargerDTO:
    """
    Update a charger's price status or price tier.
    """
    result = service.update_charger(charger_id, db, charger_patch)
    
    if not result:
        raise HTTPException(status_code=404, detail="Charger not found")
    
    return result

@fast_app.patch("/pricing-periods/{pricing_period_id}", tags=["Price setting"])
async def update_pricing_period(
    pricing_period_id: str,
    pricing_period_patch: UpdatePricingPeriodDTO,
    db: Session = Depends(get_db)
) -> PricingPeriodDTO:
    """
    Update a pricing period's details (not implemented).
    """
    raise NotImplementedError("This endpoint is not implemented yet.")

@fast_app.post("/pricing-periods", tags=["Price setting"]) 
async def create_pricing_periods(
    pricing_periods: CreatePricingPeriodsDTO,
    db: Session = Depends(get_db)
) -> PricingPeriodDTO:
    """
    Create new pricing periods for a charger (not implemented).
    """
    raise NotImplementedError("This endpoint is not implemented yet.")

@fast_app.delete("/pricing-periods", tags=["Price setting"])
async def delete_pricing_periods(
    pricing_periods: DeletePricingPeriodsDTO,
    db: Session = Depends(get_db)
) -> DeletePricingPeriodsDTO:
    """
    Delete pricing periods for a charger (not implemented).
    """
    raise NotImplementedError("This endpoint is not implemented yet.")
