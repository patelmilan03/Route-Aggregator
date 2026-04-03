from fastapi import FastAPI, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from app.schemas import RouteRequest, RouteResponse, WaypointTimeline, WeatherData
from app.services import build_itinerary
from app.config import settings
from app.database import engine, Base, get_db
from app.models import DBRoute, DBWaypoint

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.schemas import WeatherData

# Create tables on startup. In production, use Alembic for migrations instead.
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title=settings.api_title, version=settings.api_version, lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "online", "service": settings.api_title, "docs": "/docs"}

@app.post(
    "/api/v1/routes/plan", 
    response_model=RouteResponse, 
    status_code=status.HTTP_200_OK
)
async def plan_route(request: RouteRequest, db: AsyncSession = Depends(get_db)):
    if not settings.owm_api_key:
        raise HTTPException(status_code=500, detail="API key not configured.")

    try:
        # 1. Calculate the itinerary (External API calls)
        timeline = await build_itinerary(request)
        
        # 2. Persist to Database
        db_route = DBRoute(activity_name=request.activity_name)
        db.add(db_route)
        await db.flush() # Flushes to get the new route ID without committing yet

        for node in timeline:
            db_waypoint = DBWaypoint(
                route_id=db_route.id,
                sequence_order=node.sequence_order,
                location_name=node.location,
                arrival_time=node.arrival_time,
                departure_time=node.departure_time,
                is_after_sunset=node.is_after_sunset,
                error_message=node.error,
                # Extract weather safely if it exists
                temperature_celsius=node.weather.temperature_celsius if node.weather else None,
                conditions=node.weather.conditions if node.weather else None,
                # NEW: Save sunrise/sunset
                sunrise_utc=node.weather.sunrise_utc if node.weather else None,
                sunset_utc=node.weather.sunset_utc if node.weather else None,
            )
            db.add(db_waypoint)

        # Commit the transaction (saves Route and all Waypoints together)
        await db.commit()
        await db.refresh(db_route)

        # 3. Return the response
        return RouteResponse(
            id=db_route.id,
            activity_name=db_route.activity_name,
            total_waypoints=len(timeline),
            timeline=timeline
        )
        
    except Exception as e:
        await db.rollback() # Cancel database changes if something breaks
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get(
    "/api/v1/routes/{route_id}", 
    response_model=RouteResponse, 
    status_code=status.HTTP_200_OK
)
async def get_route(route_id: int, db: AsyncSession = Depends(get_db)):
    """
    Fetches a saved itinerary and all its waypoints from the database.
    """
    # Eagerly load the waypoints to avoid async lazy-loading errors
    query = select(DBRoute).options(selectinload(DBRoute.waypoints)).where(DBRoute.id == route_id)
    result = await db.execute(query)
    db_route = result.scalar_one_or_none()

    if not db_route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Route with ID {route_id} not found."
        )

    # Sort waypoints to ensure chronological order
    sorted_waypoints = sorted(db_route.waypoints, key=lambda w: w.sequence_order)
    
    # Reconstruct the Pydantic timeline list
    timeline = []
    for wp in sorted_waypoints:
        weather_obj = None
        if wp.temperature_celsius is not None:
            weather_obj = WeatherData(
                temperature_celsius=wp.temperature_celsius,
                conditions=wp.conditions,
                sunrise_utc=wp.sunrise_utc,
                sunset_utc=wp.sunset_utc
            )
            
        timeline.append(
            WaypointTimeline(
                sequence_order=wp.sequence_order,
                location=wp.location_name,
                arrival_time=wp.arrival_time,
                departure_time=wp.departure_time,
                is_after_sunset=wp.is_after_sunset,
                weather=weather_obj,
                error=wp.error_message
            )
        )

    return RouteResponse(
        id=db_route.id,
        activity_name=db_route.activity_name,
        total_waypoints=len(timeline),
        timeline=timeline
    )