import httpx
import asyncio
from datetime import timedelta
from typing import List, Dict, Any
from app.schemas import RouteRequest, WaypointTimeline, WeatherData, WaypointInput
from app.config import settings

async def fetch_weather_for_location(client: httpx.AsyncClient, waypoint: WaypointInput) -> Dict[str, Any]:
    params = {
        "lat": waypoint.lat,
        "lon": waypoint.lon,
        "appid": settings.owm_api_key,
        "units": "metric"
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
    except Exception as e:
        return {"success": False, "error": str(e)}

async def fetch_travel_time(client: httpx.AsyncClient, origin: WaypointInput, destination: WaypointInput) -> int:
    """
    Queries OSRM to get the exact driving time between two coordinates.
    Returns the duration in minutes.
    """
    # OSRM API expects coordinates in longitude,latitude format
    url = f"http://router.project-osrm.org/route/v1/driving/{origin.lon},{origin.lat};{destination.lon},{destination.lat}?overview=false"
    try:
        response = await client.get(url, timeout=5.0)
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") == "Ok" and data.get("routes"):
            duration_seconds = data["routes"][0]["duration"]
            return int(duration_seconds / 60)
            
    except Exception:
        pass # If the API fails or rate limits, we silently catch it and return the fallback below
        
    return 45 # Fallback buffer if the routing engine fails

async def build_itinerary(request: RouteRequest) -> List[WaypointTimeline]:
    async with httpx.AsyncClient() as client:
        # 1. Fetch Weather (Concurrent)
        weather_tasks = [fetch_weather_for_location(client, wp) for wp in request.waypoints]
        
        # 2. Fetch Travel Times between point A -> B, B -> C (Concurrent)
        travel_tasks = []
        for i in range(len(request.waypoints) - 1):
            travel_tasks.append(
                fetch_travel_time(client, request.waypoints[i], request.waypoints[i+1])
            )
        
        # Await all external requests simultaneously
        weather_results = await asyncio.gather(*weather_tasks)
        travel_times = await asyncio.gather(*travel_tasks)

    timeline = []
    current_time = request.start_time

    for index, (waypoint, weather_res) in enumerate(zip(request.waypoints, weather_results)):
        arrival = current_time
        departure = arrival + timedelta(minutes=waypoint.estimated_duration_mins)
        
        after_sunset = False
        weather_data = None
        
        if weather_res["success"]:
            weather_data = weather_res["data"]
            
            # New logic: Extracts ONLY the clock time (HH:MM:SS) and compares them
            arrival_time_only = arrival.time()
            sunset_time_only = weather_data.sunset_utc.time()
            
            if arrival_time_only >= sunset_time_only:
                after_sunset = True

        node = WaypointTimeline(
            sequence_order=index + 1,
            location=waypoint.name,
            arrival_time=arrival,
            departure_time=departure,
            is_after_sunset=after_sunset,
            weather=weather_data,
            error=weather_res.get("error")
        )
        timeline.append(node)
        
        # Add the dynamic travel time to reach the NEXT waypoint (if one exists)
        if index < len(travel_times):
            current_time = departure + timedelta(minutes=travel_times[index])

    return timeline