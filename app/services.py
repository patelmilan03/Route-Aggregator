import httpx
import asyncio
from datetime import timedelta
from typing import List, Dict, Any
from app.schemas import RouteRequest, WaypointTimeline, WeatherData, WaypointInput
from app.config import settings

async def fetch_weather_for_location(client: httpx.AsyncClient, waypoint: WaypointInput) -> Dict[str, Any]:
    """
    Fetches weather data using precise GPS coordinates.
    """
    params = {
        "lat": waypoint.lat,
        "lon": waypoint.lon,
        "appid": settings.owm_api_key,
        "units": "metric" # Force Celsius
    }
    try:
        response = await client.get(settings.owm_base_url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        return {
            "success": True,
            "data": WeatherData(
                temperature_celsius=data["main"]["temp"],
                conditions=data["weather"][0]["description"].title(),
                sunrise_utc=data["sys"]["sunrise"],
                sunset_utc=data["sys"]["sunset"]
            )
        }
    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"API Error: {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"success": False, "error": f"Network error occurred: {str(e)}"}

async def build_itinerary(request: RouteRequest) -> List[WaypointTimeline]:
    """
    Orchestrates the concurrent fetching of weather data and calculates timeline.
    """
    async with httpx.AsyncClient() as client:
        # Pass the full waypoint object instead of just the string
        tasks = [fetch_weather_for_location(client, wp) for wp in request.waypoints]
        weather_results = await asyncio.gather(*tasks)

    timeline = []
    current_time = request.start_time
    travel_buffer_mins = 45 

    for index, (waypoint, weather_res) in enumerate(zip(request.waypoints, weather_results)):
        arrival = current_time
        departure = arrival + timedelta(minutes=waypoint.estimated_duration_mins)
        
        node = WaypointTimeline(
            sequence_order=index + 1,
            location=waypoint.name, # Use the new 'name' field
            arrival_time=arrival,
            departure_time=departure,
            weather=weather_res["data"] if weather_res["success"] else None,
            error=weather_res.get("error")
        )
        timeline.append(node)
        current_time = departure + timedelta(minutes=travel_buffer_mins)

    return timeline