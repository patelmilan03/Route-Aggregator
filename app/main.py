from fastapi import FastAPI, HTTPException, status, Depends, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.schemas import RouteRequest, RouteResponse, WaypointTimeline, WeatherData
from app.services import build_itinerary
from app.config import settings
from app.database import engine, Base, get_db
from app.models import DBRoute, DBWaypoint
from app.routers import route_planner

# Define the header name we expect
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == settings.api_key:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate API Key",
    )

# Create tables on startup. In production, use Alembic for migrations instead.
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title=settings.api_title, version=settings.api_version, lifespan=lifespan)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Route Aggregator API</title>
        <style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
                background-color: #0f172a; 
                color: #f8fafc; 
                display: flex; 
                justify-content: center; 
                align-items: center; 
                height: 100vh; 
                margin: 0; 
            }
            .container { 
                text-align: center; 
                background: #1e293b; 
                padding: 3rem; 
                border-radius: 12px; 
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3); 
                border: 1px solid #334155; 
                max-width: 400px;
            }
            h1 { margin-top: 0; margin-bottom: 0.5rem; color: #38bdf8; font-size: 1.5rem; }
            p { color: #94a3b8; margin-bottom: 2rem; font-size: 0.95rem; line-height: 1.5; }
            .btn { 
                background-color: #0ea5e9; 
                color: white; 
                padding: 12px 24px; 
                text-decoration: none; 
                border-radius: 6px; 
                font-weight: 600; 
                transition: background-color 0.2s; 
                display: inline-block;
            }
            .btn:hover { background-color: #0284c7; }
            .status { 
                display: inline-flex; 
                align-items: center; 
                gap: 8px; 
                font-size: 0.85rem; 
                color: #10b981; 
                margin-bottom: 1.5rem; 
                font-weight: 600;
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }
            .dot { 
                width: 8px; 
                height: 8px; 
                background-color: #10b981; 
                border-radius: 50%; 
                box-shadow: 0 0 8px #10b981; 
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="status"><div class="dot"></div> System Online</div>
            <h1>Logistics & Route Aggregator</h1>
            <p>Core routing engine and weather aggregation service running securely in the cloud.</p>
            <a href="/docs" class="btn">Explore API Documentation</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)
@app.post("/api/v1/routes/plan", response_model=RouteResponse, dependencies=[Depends(get_api_key)])
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

