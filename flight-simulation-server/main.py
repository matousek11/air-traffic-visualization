"""
Houses api for control of BlueSky simulation
"""

from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .services.bluesky_service import BlueskyService
from .services.mtcd_toolkit import MtcdToolkit
from .models.flight import Flight
from .models.flight_with_flight_plan import FlightWithFlightPlan
from .models.waypoint import Waypoint
from .models.closest_approach_point import ClosestApproachPoint

bluesky_service = BlueskyService()
bluesky_service.start_simulation()
bluesky_service.run_simulation_thread()

mtcd_toolkit = MtcdToolkit(bluesky_service)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/flights")
def add_flight(flight: Flight) -> Flight:
    """
    Adds new flight to BlueSky simulation and return that flight
    """
    bluesky_service.create_flight(flight)
    return flight

@app.get(
    "/flights",
    response_model=List[FlightWithFlightPlan]|FlightWithFlightPlan
)
def get_flight(
        flight_id: str|None = None
) -> List[FlightWithFlightPlan]|FlightWithFlightPlan:
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

@app.get("/closest-approach-point")
def get_closest_approach_point(
        first_flight_id: str,
        second_flight_id: str
) -> ClosestApproachPoint:
    """
    Calculates the closest approach point between two flights and their distance
    """
    if first_flight_id == second_flight_id:
        raise ValueError("First flight id must be different")

    [
        horizontal_distance,
        vertical_distance,
        time_to_closest_approach_point,
        middle_point_lat,
        middle_point_lon,
        middle_point_fl,
    ] = mtcd_toolkit.calculate_closest_approach_point(
        first_flight_id, second_flight_id
    )

    return ClosestApproachPoint(
        first_flight_id=first_flight_id,
        second_flight_id=second_flight_id,
        horizontal_distance=horizontal_distance,
        vertical_distance=vertical_distance,
        time_to_closest_approach=time_to_closest_approach_point,
        middle_point_lat=middle_point_lat,
        middle_point_lon=middle_point_lon,
        middle_point_fl=middle_point_fl,
    )
