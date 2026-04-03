from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class DBRoute(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, index=True)
    activity_name = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # One Route has many Waypoints
    waypoints = relationship("DBWaypoint", back_populates="route", cascade="all, delete-orphan")

class DBWaypoint(Base):
    __tablename__ = "waypoints"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id"))
    sequence_order = Column(Integer)
    location_name = Column(String)
    arrival_time = Column(DateTime)
    departure_time = Column(DateTime)
    
    # Weather & Logic Flags
    temperature_celsius = Column(Float, nullable=True)
    conditions = Column(String, nullable=True)
    # Add these right below conditions
    sunrise_utc = Column(DateTime, nullable=True)
    sunset_utc = Column(DateTime, nullable=True)
    is_after_sunset = Column(Boolean, default=False)
    error_message = Column(String, nullable=True)

    route = relationship("DBRoute", back_populates="waypoints")