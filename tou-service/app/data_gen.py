from shapely.geometry import Point
from geoalchemy2.shape import from_shape
from app.database.models import Region, Charger, PricingPeriod, PricingPeriodStatus, ChargerPriceStatus
from sqlalchemy.orm import Session
import random
import geopandas as gpd
import gc
from datetime import time

def generate_random_point(polygon):
    minx, miny, maxx, maxy = polygon.bounds
    while True:
        point = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
        if polygon.contains(point):
            return point
        
def generate_points_within_county(gdf, county_name, num_points):
    county_gdf = gdf[gdf['NAME'] == county_name]

    if len(county_gdf) != 1:
        raise ValueError(f"County '{county_name}' has row number different than 1.")
    
    county_row = county_gdf.iloc[0]

    geom = county_row["geometry"]
    polygon = geom if geom.geom_type == "Polygon" else geom.convex_hull
    points = [generate_random_point(polygon) for _ in range(num_points)]

    return points

def generate_random_price_schedule(charger: Charger, region: Region):
    num_periods = random.randint(4, 7)

    # [(start_time, end_time)]
    periods = []

    if num_periods == 4:
        periods = [
            (time(hour=0), time(hour=9)),
            (time(hour=9), time(hour=12)),
            (time(hour=12), time(hour=15)),
            (time(hour=15), time(hour=0))
        ]
    elif num_periods == 5:
        periods = [
            (time(hour=0), time(hour=8)),
            (time(hour=8), time(hour=11)),
            (time(hour=11), time(hour=15)),
            (time(hour=15), time(hour=18)),
            (time(hour=18), time(hour=0))
        ]
    elif num_periods == 6:
        periods = [
            (time(hour=0), time(hour=7)),
            (time(hour=7), time(hour=10)),
            (time(hour=10), time(hour=13)),
            (time(hour=13), time(hour=18)),
            (time(hour=18), time(hour=21)),
            (time(hour=21), time(hour=0))
        ]
    elif num_periods == 7:
        periods = [
            (time(hour=0), time(hour=6)),
            (time(hour=6), time(hour=9)),
            (time(hour=9), time(hour=12)),
            (time(hour=12), time(hour=15)),
            (time(hour=15), time(hour=18)),
            (time(hour=18), time(hour=21)),
            (time(hour=21), time(hour=0))
        ]

    pricing_periods = []
    
    for period in periods:
        start_time, end_time = period
        demand_index = random.randint(1, 5)
        price_per_kwh = round(region.region_price_tier * 0.05 + \
            charger.charger_price_tier * 0.02 + \
            demand_index * 0.03,
            2)
        
        pricing_period = PricingPeriod(
            charger_id=charger.id,
            start_time=start_time,
            end_time=end_time,
            demand_index=demand_index,
            price_per_kwh=price_per_kwh,
            status=PricingPeriodStatus.UP_TO_DATE
        )
        
        pricing_periods.append(pricing_period)
        
    return pricing_periods
    

def generate_data_for_alameda_contra_costa(db: Session):
    zip_path = "/data/tl_2024_us_county.zip"
    gdf = gpd.read_file(f"zip://{zip_path}")

    target_counties = gdf[gdf['NAME'].isin(["Alameda", "Contra Costa"])]
    
    # Clean up up memory
    del gdf
    gc.collect()

    counties_points = {}
    counties_points["alameda"] = generate_points_within_county(target_counties, "Alameda", 108)
    counties_points["contra_costa"] = generate_points_within_county(target_counties, "Contra Costa", 78)
    
    region_alameda_ca = Region(
        name="Alameda County",
        state_code="CA",
        region_price_tier=4
    )
    region_contra_costa_ca = Region(
        name="Contra Costa County",
        state_code="CA",
        region_price_tier=3
    )
    region_az = Region(
        name="Maricopa County",
        state_code="AZ",
        region_price_tier=2
    )
    db.add_all([region_alameda_ca, region_contra_costa_ca, region_az])
    db.commit()
    
    chargers = []
    
    for county in ["alameda", "contra_costa"]:
        for point in counties_points[county]:
            charger = Charger(
                region_id=region_alameda_ca.id if county == "alameda" else region_contra_costa_ca.id,
                location=from_shape(point, srid=4326),
                time_zone="America/Los_Angeles",
                in_use=bool(random.getrandbits(1)),
                charger_price_tier=random.randint(1, 5),
                price_status=ChargerPriceStatus.UP_TO_DATE,
                operational=True
            )
            db.add(charger)
            chargers.append(charger)
    
    db.commit()

    for charger in chargers:
        region = region_alameda_ca if charger.region_id == region_alameda_ca.id else region_contra_costa_ca
        pricing_periods = generate_random_price_schedule(charger, region)
        
        for pricing_period in pricing_periods:
            db.add(pricing_period)
    
    db.commit()
    
    return True
