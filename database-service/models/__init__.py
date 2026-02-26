"""Database models for air traffic visualization system."""

from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Import all models to ensure they are registered with Base
from .mtcd_event import MTCDEvent
from .flight import Flight
from .flight_position import FlightPosition
from .fix import Fix
from .airway import Airway
from .airport import Airport
from .nav import Nav

__all__ = ["Base", "MTCDEvent", "Flight", "FlightPosition", "Fix", "Airway", "Airport", "Nav"]
