"""
Houses api for control of BlueSky simulation
"""

from typing import List

from fastapi import FastAPI, HTTPException
from .services.bluesky_service import BlueskyService
from .models.flight import Flight
from .models.flight_with_flight_plan import FlightWithFlightPlan
from .models.waypoint import Waypoint

bluesky_service = BlueskyService()
bluesky_service.start_simulation()
bluesky_service.run_simulation_thread()

app = FastAPI()

#bluesky_service.create_flight("AAL101", "B763", 50, 14, 90, 100, 250)
#bluesky_service.create_flight("DAL202", "B763", 49.95, 14.05, 0, 100, 280)
#bluesky_service.get_flight_position()

@app.post("/flights")
def add_flight(flight: Flight) -> Flight:
    """
    Adds new flight to BlueSky and return that flight
    """
    bluesky_service.create_flight(flight)
    return flight

@app.get("/flights", response_model=List[FlightWithFlightPlan]|FlightWithFlightPlan)
def get_flight(flight_id: str|None = None) -> List[FlightWithFlightPlan]|FlightWithFlightPlan:
    """
    Lists all currently running flight in BlueSky
    """
    if flight_id is None:
        return bluesky_service.get_flights()

    flight = bluesky_service.get_flight(flight_id)
    if flight is None:
        raise HTTPException(status_code=404, detail="Flight not found")

    return flight

@app.post("/flights/{flight_id}/waypoints")
def add_waypoint(flight_id: str, waypoint: Waypoint) -> Waypoint:
    """
    Adds new waypoint as last one into flight's flight plan
    """
    bluesky_service.add_waypoint(flight_id, waypoint)

    return waypoint


@app.post("/reset-simulation")
def reset_simulation():
    """
    Reset BlueSky simulation
    """
    bluesky_service.reset_simulation()
