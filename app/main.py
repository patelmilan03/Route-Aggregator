
from fastapi import FastAPI, HTTPException, status
from app.schemas import RouteRequest, RouteResponse
from app.services import build_itinerary
from app.config import settings

app = FastAPI(title=settings.api_title, version=settings.api_version)
@app.get("/")
async def root():
    """
    Health check endpoint to verify the API is running.
    """
    return {
        "status": "online", 
        "service": settings.api_title,
        "docs": "/docs"
    }
    
@app.post(
    "/api/v1/routes/plan", 
    response_model=RouteResponse, 
    status_code=status.HTTP_200_OK,
    summary="Generate a weather-aware itinerary"
)
async def plan_route(request: RouteRequest):
    """
    Accepts a route of waypoints, fetches weather concurrently, 
    and returns a sequenced timeline.
    """
    if not settings.owm_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OpenWeatherMap API key is not configured on the server."
        )

    if not request.waypoints:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one waypoint must be provided."
        )

    try:
        timeline = await build_itinerary(request)
        
        return RouteResponse(
            activity_name=request.activity_name,
            total_waypoints=len(timeline),
            timeline=timeline
        )
    except Exception as e:
        # Catch unexpected errors to prevent app crashes and return clean JSON
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while processing the route: {str(e)}"
        )