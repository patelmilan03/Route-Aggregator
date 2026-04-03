from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class WaypointInput(BaseModel):
    name: str = Field(..., description="The name of the landmark or location")
    lat: float = Field(..., description="Latitude of the location")
    lon: float = Field(..., description="Longitude of the location")
    estimated_duration_mins: int = Field(60, description="How long you plan to stay here")

class RouteRequest(BaseModel):
    activity_name: str = Field(..., example="Weekend Photowalk")
    start_time: datetime = Field(default_factory=datetime.utcnow, description="ISO 8601 start time")
    waypoints: List[WaypointInput]

class WeatherData(BaseModel):
    temperature_celsius: float
    conditions: str
    sunrise_utc: datetime
    sunset_utc: datetime

class WaypointTimeline(BaseModel):
    sequence_order: int
    location: str
    arrival_time: datetime
    departure_time: datetime
    is_after_sunset: bool = False  # NEW FIELD
    weather: Optional[WeatherData] = None
    error: Optional[str] = None

class RouteResponse(BaseModel):
    id: int  # NEW FIELD (Database ID)
    activity_name: str
    total_waypoints: int
    timeline: List[WaypointTimeline]