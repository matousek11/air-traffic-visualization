"""
Houses api for control of BlueSky simulation
"""

from typing import List
import logging

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .services.bluesky_service import BlueskyService
from common.helpers.mtcd_toolkit import MtcdToolkit
from .models.flight import Flight
from .models.flight_detail_response import FlightDetailResponse
from .models.waypoint import Waypoint
from .models.closest_approach_point import ClosestApproachPoint
from .models.wind import Wind
from .models.speed_action import SpeedAction

logger = logging.getLogger(__name__)

bluesky_service = BlueskyService()
bluesky_service.start_simulation()
bluesky_service.run_simulation_thread()

mtcd_toolkit = MtcdToolkit()

# Database service URL - can be configured via env variable
DATABASE_SERVICE_URL = "http://localhost:8002"

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
    response_model=List[FlightDetailResponse] | FlightDetailResponse
)
def get_flight(
        flight_id: str|None = None
) -> List[FlightDetailResponse] | FlightDetailResponse:
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

@app.post("/simulation/wind")
def set_wind(wind: Wind) -> Wind:
    """Sets wind conditions for the simulation"""
    bluesky_service.set_wind(wind)

    return wind

@app.get("/simulation/speed")
def get_simulation_speed() -> dict:
    """Get current simulation speed"""
    return {
        "current_speed": bluesky_service.current_speed
    }

@app.post("/simulation/speed")
def set_simulation_speed(action: SpeedAction) -> dict:
    """Increase or decrease simulation speed by 1 unit"""
    bluesky_service.set_speed(action.increase)
    
    return {
        "status": "success", 
        "action": "increase" if action.increase else "decrease",
        "current_speed": bluesky_service.current_speed
    }

@app.post("/reset-simulation")
def reset_simulation() -> dict:
    """
    Reset BlueSky simulation and database
    """
    # Reset BlueSky simulation
    bluesky_service.reset_simulation()
    
    # Call database service to reset database
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.delete(f"{DATABASE_SERVICE_URL}/reset-for-new-simulation")
            response.raise_for_status()
            logger.info("Database reset successfully")
    except httpx.HTTPError as e:
        logger.error(f"Failed to reset database: {e}")
        # Don't fail the whole operation if database reset fails
        # BlueSky is already reset
    
    return {"status": "success", "message": "Simulation and database reset"}
    

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

    # Get flight objects from BlueSky service
    flight_1 = bluesky_service.get_flight(first_flight_id)
    flight_2 = bluesky_service.get_flight(second_flight_id)

    if flight_1 is None:
        raise HTTPException(status_code=404, detail=f"Flight {first_flight_id} not found")
    if flight_2 is None:
        raise HTTPException(status_code=404, detail=f"Flight {second_flight_id} not found")

    # Calculate closest approach point
    result = mtcd_toolkit.calculate_closest_approach_point(flight_1, flight_2)
    
    if result is None:
        raise HTTPException(status_code=400, detail="Cannot calculate closest approach point")

    [
        horizontal_distance,
        vertical_distance,
        time_to_closest_approach_point,
        middle_point_lat,
        middle_point_lon,
        middle_point_fl,
    ] = result

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
