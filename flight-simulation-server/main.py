"""
Houses api for control of BlueSky simulation
"""

import types
from typing import List

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from common.helpers.logging_service import LoggingService
from common.helpers.mtcd_pipeline import MtcdPipeline
from common.models.flight_position_adapter import FlightPositionAdapter
from .services.bluesky_service import BlueskyService
from .models.flight import Flight
from .models.flight_detail_response import FlightDetailResponse
from .models.waypoint import Waypoint
from .models.conflicts_response import (
    ClosestApproachPointsResponse,
    ConflictItem,
)
from .models.wind import Wind
from .models.speed_action import SpeedAction

logger = LoggingService.get_logger(__name__)

bluesky_service = BlueskyService()
bluesky_service.start_simulation()
bluesky_service.run_simulation_thread()

mtcd_pipeline = MtcdPipeline()

# Database service URL - can be configured via env variable
DATABASE_SERVICE_URL = "http://localhost:8002"

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace it with specific origins
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
            url = f"{DATABASE_SERVICE_URL}/reset-for-new-simulation"
            response = client.delete(url)
            response.raise_for_status()
            logger.info("Database reset successfully")
    except httpx.HTTPError as e:
        logger.error("Failed to reset database: %s", e)
        # Don't fail the whole operation if database reset fails
        # BlueSky is already reset

    return {"status": "success", "message": "Simulation and database reset"}


@app.get("/closest-approach-point")
def get_closest_approach_point(
    first_flight_id: str,
    second_flight_id: str,
) -> ClosestApproachPointsResponse:
    """
    Detects conflicts between two flights via MTCD pipeline.

    Returns zero, one, or multiple conflicts (predicted closest approach points)
    for the given pair. Uses flight plan (waypoints) when available for
    segment-based detection.
    """
    if first_flight_id == second_flight_id:
        raise HTTPException(
            status_code=400,
            detail="First flight id must be different from second flight id",
        )

    flight_1 = bluesky_service.get_flight(first_flight_id)
    flight_2 = bluesky_service.get_flight(second_flight_id)

    if flight_1 is None:
        raise HTTPException(
            status_code=404,
            detail=f"Flight {first_flight_id} not found",
        )
    if flight_2 is None:
        raise HTTPException(
            status_code=404,
            detail=f"Flight {second_flight_id} not found",
        )

    adapter_1 = _flight_detail_to_position_adapter(flight_1)
    adapter_2 = _flight_detail_to_position_adapter(flight_2)
    detected_conflicts = mtcd_pipeline.run_mtcd(adapter_1, adapter_2)

    conflicts = [
        ConflictItem(
            horizontal_distance=c.horizontal_distance,
            vertical_distance=c.vertical_distance,
            time_to_closest_approach=c.time_to_closest_approach,
            time_to_conflict_entry=c.time_to_conflict_entry,
            time_to_conflict_exit=c.time_to_conflict_exit,
            middle_point_lat=c.middle_point.lat,
            middle_point_lon=c.middle_point.lon,
            middle_point_fl=c.middle_point.flight_level,
        )
        for c in detected_conflicts
    ]

    return ClosestApproachPointsResponse(
        first_flight_id=first_flight_id,
        second_flight_id=second_flight_id,
        conflicts=conflicts,
    )

def _flight_detail_to_position_adapter(
    detail: FlightDetailResponse,
) -> FlightPositionAdapter:
    """
    Convert BlueSky FlightDetailResponse to FlightPositionAdapter for MTCD.

    Uses route_string from detail (built with DCT at service level); no joining
    in main.

    Args:
        detail: Flight detail from BlueSky service.

    Returns:
        FlightPositionAdapter instance usable by MtcdPipeline.run_mtcd.
    """
    pos = types.SimpleNamespace(
        lat=detail.lat,
        lon=detail.lon,
        flight_level=detail.flight_level,
        ground_speed_kt=detail.speed,
        heading=detail.heading,
        track_heading=detail.track_heading,
        route=detail.route_string,
        vertical_rate_fpm=detail.vertical_speed,
    )
    return FlightPositionAdapter(pos, detail.flight_id)

