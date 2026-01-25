"""Database models for air traffic visualization system."""

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Import all models to ensure they are registered with Base
from .mtcd_event import MTCDEvent
from .flight import Flight
from .flight_position import FlightPosition

__all__ = ["Base", "MTCDEvent", "Flight", "FlightPosition"]
