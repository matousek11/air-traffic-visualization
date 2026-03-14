"""
Module houses service that controls BlueSky simulation
"""

from typing import List
import time
import threading

import bluesky as bs
import numpy as np
from bluesky import stack

from common.helpers.logging_service import LoggingService
from .flight_plan_service import FlightPlanService
from ..models.flight import Flight
from ..models.flight_detail_response import FlightDetailResponse
from ..models.waypoint import Waypoint
from ..models.wind import Wind

logger = LoggingService.get_logger(__name__)

class BlueskyService:
    """
    Handles control and updates of Bluesky simulation
    """
    def __init__(self):
        # Initialize BlueSky in simulation mode without networking
        bs.init(mode="sim", detached=False)
        self._running = False
        self._sim_thread = None
        self.flight_plan_service = FlightPlanService()
        self.current_speed = 1.0

    def __del__(self):
        self.stop_simulation_thread()

    def run_simulation_thread(self, interval: float = 0.05):
        """Start background thread to step simulation automatically."""
        if self._sim_thread is None or not self._sim_thread.is_alive():
            self._running = True
            self._sim_thread = threading.Thread(
                target=self.run_simulation_time, args=(interval,), daemon=True
            )
            self._sim_thread.start()
            logger.info("Simulation thread started.")

    def run_simulation_time(self, base_interval=0.05):
        """Advance the simulation every `base_interval` seconds, adjusted by speed multiplier."""
        while self._running:
            steps = max(1, int(self.current_speed))
            for _ in range(steps):
                bs.sim.step()
            
            time.sleep(base_interval)

    def stop_simulation_thread(self):
        """Stops BlueSky simulation and reset it"""
        self._running = False
        if self._sim_thread:
            self._sim_thread.join()
            logger.info("Simulation thread stopped.")
            self.flight_plan_service.reset()

    @staticmethod
    def start_simulation():
        """Start BlueSky simulation"""
        stack.stack("OP")

    def reset_simulation(self):
        """Reset BlueSky simulation"""
        stack.stack("RESET")
        self.flight_plan_service.reset()
        logger.info("Simulation reset")

    @staticmethod
    def create_flight(flight: Flight) -> None:
        logger.info("Creating flight %s...", flight.get_creation_string())
        stack.stack(flight.get_creation_string())
        stack.stack(flight.get_vertical_speed())
        stack.stack(f"{flight.flight_id} LNAV ON")

    def get_flight(self, flight_id: str) -> FlightDetailResponse | None:
        """Load one flight"""
        try:
            idx = bs.traf.id.index(flight_id)
        except ValueError:
            logger.info("Aircraft %s not found", flight_id)
            return None

        lat = bs.traf.lat[idx]
        lon = bs.traf.lon[idx]
        flight_level = bs.traf.alt[idx] * 0.03281 # from meters to fl
        hdg = bs.traf.hdg[idx]
        track_heading = bs.traf.trk[idx]
        vertical_speed = bs.traf.vs[idx] * 3.28084 * 60  # m/s to ft/min
        gs = bs.traf.gs[idx] * 1.94384449 # from km/h to kts
        flight_plan = self.flight_plan_service.get_flight_plan(flight_id)
        route_string = self.flight_plan_service.get_route_string(flight_id)
        # Get wind on position of plane (getdata returns windnorth, windeast)
        alt_ft = int(bs.traf.alt[idx] * 3.28084)
        windnorth, windeast = bs.traf.wind.getdata(bs.traf.lat[idx], bs.traf.lon[idx], bs.traf.alt[idx])
        wind_speed = np.sqrt(windnorth ** 2 + windeast ** 2) * 1.944
        # Wind FROM direction: arctan2(-east, -north) for aviation bearing
        wind_heading = (np.degrees(np.arctan2(-windeast, -windnorth)) + 360) % 360
        return FlightDetailResponse(
            flight_id=flight_id,
            plane_type=bs.traf.type[idx],
            lat=lat,
            lon=lon,
            flight_level=int(flight_level),
            heading=int(hdg),
            track_heading=int(track_heading),
            speed=int(gs),
            vertical_speed=int(vertical_speed),
            flight_plan=flight_plan,
            route_string=route_string,
            wind=Wind(heading=wind_heading, speed=wind_speed, lat=lat, lon=lon, altitude=alt_ft)
        )

    def get_flights(self) -> List[FlightDetailResponse]:
        """Loads all flights"""
        flights = []

        for i in range(bs.traf.ntraf):
            acid = bs.traf.id[i]
            lat = bs.traf.lat[i]
            lon = bs.traf.lon[i]
            flight_level = bs.traf.alt[i] * 0.03281 # from meters to fl
            hdg = bs.traf.hdg[i]
            track_heading = bs.traf.trk[i]
            vertical_speed = bs.traf.vs[i] * 3.28084 * 60 # m/s to ft/min
            gs = bs.traf.gs[i] * 1.94384449 # from km/h to kts
            flight_plan = self.flight_plan_service.get_flight_plan(acid)
            route_string = self.flight_plan_service.get_route_string(acid)
            # Get wind on position of plane (getdata returns windnorth, windeast)
            alt_ft = int(bs.traf.alt[i] * 3.28084)
            windnorth, windeast = bs.traf.wind.getdata(bs.traf.lat[i], bs.traf.lon[i], bs.traf.alt[i])
            wind_speed = np.sqrt(windnorth ** 2 + windeast ** 2) * 1.944
            # Wind FROM direction: arctan2(-east, -north) for aviation bearing
            wind_heading = (np.degrees(np.arctan2(-windeast, -windnorth)) + 360) % 360
            flights.append(
                FlightDetailResponse(
                    flight_id=acid,
                    plane_type=bs.traf.type[i],
                    lat=lat,
                    lon=lon,
                    flight_level=int(flight_level),
                    heading=int(hdg),
                    track_heading=int(track_heading),
                    speed=int(gs),
                    vertical_speed=int(vertical_speed),
                    flight_plan=flight_plan,
                    route_string=route_string,
                    wind=Wind(heading=wind_heading, speed=wind_speed, lat=lat, lon=lon, altitude=alt_ft)
                )
            )

        return flights

    def add_waypoint(
            self,
            flight_id: str,
            waypoint: Waypoint
    ) -> Waypoint:
        """Adds a waypoint as the last one to the flight"""
        self.flight_plan_service.add_waypoint_to_flight_plan(
            flight_id, waypoint
        )
        stack.stack(
            f"{flight_id} ADDWPT {waypoint.name} FL{waypoint.flight_level} {waypoint.speed}"
        )

        return waypoint

    def set_wind(self, wind: Wind) -> None:
        """Sets wind conditions for the simulation"""
        stack.stack(f"WIND {wind.lat} {wind.lon} {wind.altitude} {wind.heading} {wind.speed}")

    def set_speed(self, increase: bool) -> None:
        """Decreases or increases the speed of the simulation by controlling loop frequency"""
        if increase is True:
            self.current_speed += 1.0
        elif self.current_speed > 1.0:
            self.current_speed -= 1.0
        else:
            return  # Cannot decrease below 1.0
        
        logger.info("Simulation speed set to %sx", self.current_speed)