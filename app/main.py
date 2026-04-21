from fastapi import FastAPI, HTTPException, status, Depends, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import asyncio
import httpx
from app.schemas import RouteRequest, RouteResponse, WaypointTimeline, WeatherData
from app.services import build_itinerary
from app.config import settings
from app.database import engine, Base, get_db
from app.models import DBRoute, DBWaypoint
# from app.routers import route_planner

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

# --- KEEP-ALIVE DAEMON ---
async def keep_alive():
    # Replace this with your exact Render URL
    url = "https://route-aggregator-api.onrender.com" 
    
    async with httpx.AsyncClient() as client:
        while True:
            await asyncio.sleep(10 * 60)  # Pauses the loop for 10 minutes
            try:
                await client.get(url)
                print("Keep-alive ping successful.")
            except Exception as e:
                print(f"Keep-alive ping failed: {e}")

@app.on_event("startup")
async def startup_event():
    # Spawns the daemon in the background without blocking the main API
    asyncio.create_task(keep_alive())
# -------------------------

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
                min-height: 100vh; 
                margin: 0; 
                padding: 2rem;
            }
            .container { 
                background: #1e293b; 
                padding: 3rem; 
                border-radius: 12px; 
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3); 
                border: 1px solid #334155; 
                max-width: 600px;
            }
            h1 { margin-top: 0; color: #38bdf8; font-size: 1.8rem; text-align: center; }
            h2 { color: #e2e8f0; font-size: 1.2rem; margin-top: 2rem; border-bottom: 1px solid #334155; padding-bottom: 0.5rem; }
            p { color: #94a3b8; font-size: 0.95rem; line-height: 1.6; }
            .btn { 
                background-color: #0ea5e9; 
                color: white; 
                padding: 12px 24px; 
                text-decoration: none; 
                border-radius: 6px; 
                font-weight: 600; 
                transition: background-color 0.2s; 
                display: block;
                text-align: center;
                margin-top: 2.5rem;
            }
            .btn:hover { background-color: #0284c7; }
            .status { 
                display: flex; 
                justify-content: center;
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
            <div class="status"><div class="dot"></div> System Online & Monitoring</div>
            <h1>Logistics & Route Aggregator</h1>
            
            <h2>The Mission</h2>
            <p>An automated logistics engine designed to ingest a sequence of geographical waypoints, calculate dynamic driving times between them using OSRM, and concurrently aggregate localized weather and daylight data to generate a precision travel itinerary.</p>
            
            <h2>The Problem</h2>
            <p>Standard travel planning tools rely on static time buffers and fail to account for real-world driving distances or localized daylight constraints. Furthermore, sequentially querying multiple third-party services (routing, weather) creates massive latency bottlenecks in backend systems.</p>

            <h2>The Origin</h2>
            <p>This architecture was born out of necessity while mapping out a complex Spiti Valley circuit. Attempting to manually schedule a logical, multi-day route from Rishikesh to Manali exposed a critical flaw: standard maps couldn't accurately forecast localized mountain driving times combined with strict pre-sunset arrival constraints. This API automates that exact safety and logistical calculation.</p>
            
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

