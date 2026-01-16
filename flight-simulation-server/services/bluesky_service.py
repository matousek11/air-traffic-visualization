"""
Module houses service that controls BlueSky simulation
"""

from typing import List
import time
import threading

import bluesky as bs
import bluesky.stack as stack
from .flight_plan_service import FlightPlanService
from ..models.flight import Flight
from ..models.flight_with_flight_plan import FlightWithFlightPlan
from ..models.waypoint import Waypoint

class BlueskyService:
    def __init__(self):
        # Initialize BlueSky in simulation mode without networking
        bs.init(mode='sim', detached=False)
        self._running = False
        self._sim_thread = None
        self.flight_plan_service = FlightPlanService()

    def __del__(self):
        self.stop_simulation_thread()

    def run_simulation_thread(self, interval: float = 1):
        """Start background thread to step simulation automatically."""
        if self._sim_thread is None or not self._sim_thread.is_alive():
            self._running = True
            self._sim_thread = threading.Thread(target=self.run_simulation_time, args=(interval,), daemon=True)
            self._sim_thread.start()
            print("Simulation thread started.")

    def run_simulation_time(self, interval=1.0):
        """Advance the simulation every `interval` seconds."""
        while self._running:
            bs.sim.step()
            time.sleep(interval)

    def stop_simulation_thread(self):
        """Stops BlueSky simulation and reset it"""
        self._running = False
        if self._sim_thread:
            self._sim_thread.join()
            print("Simulation thread stopped.")
            self.flight_plan_service.reset()

    @staticmethod
    def start_simulation():
        """Start BlueSky simulation"""
        stack.stack("OP")

    def reset_simulation(self):
        """Reset BlueSky simulation"""
        stack.stack("RESET")
        self.flight_plan_service.reset()
        print("Simulation reset")

    @staticmethod
    def create_flight(flight: Flight) -> None:
        print(f"Creating flight {flight.flight_id}...")
        stack.stack(flight.get_creation_string())
        stack.stack(f"{flight.flight_id} VNAV ON")
        stack.stack(f"{flight.flight_id} LNAV ON")

    def get_flight(self, flight_id: str) -> FlightWithFlightPlan|None:
        """Load one flight"""
        print(bs.traf.id)
        try:
            idx = bs.traf.id.index(flight_id)
        except ValueError:
            print(f"Aircraft {flight_id} not found")
            return None

        lat = bs.traf.lat[idx]
        lon = bs.traf.lon[idx]
        alt = bs.traf.alt[idx]
        hdg = bs.traf.hdg[idx]
        gs = bs.traf.gs[idx] * 1.94384449
        flight_plan = self.flight_plan_service.get_flight_plan(flight_id)
        return FlightWithFlightPlan(
            flight_id=flight_id,
            plane_type=bs.traf.type[idx],
            lat=lat,
            lon=lon,
            flight_level=int(alt),
            heading=int(hdg),
            speed=int(gs),
            flight_plan=flight_plan
        )

    def get_flights(self) -> List[FlightWithFlightPlan]:
        """Loads all flights"""
        flights = []

        for i in range(bs.traf.ntraf):
            acid = bs.traf.id[i]
            lat = bs.traf.lat[i]
            lon = bs.traf.lon[i]
            alt = bs.traf.alt[i]
            hdg = bs.traf.hdg[i]
            gs = bs.traf.gs[i] * 1.94384449
            flight_plan = self.flight_plan_service.get_flight_plan(acid)
            flights.append(
                FlightWithFlightPlan(
                    flight_id=acid,
                    plane_type=bs.traf.type[i],
                    lat=lat,
                    lon=lon,
                    flight_level=int(alt),
                    heading=int(hdg),
                    speed=int(gs),
                    flight_plan=flight_plan
                )
            )

        return flights

    def add_waypoint(self, flight_id: str, waypoint: Waypoint) -> Waypoint:
        """Adds a waypoint as the last one to the flight"""
        self.flight_plan_service.add_waypoint_to_flight_plan(flight_id, waypoint)
        stack.stack(f"{flight_id} ADDWPT {waypoint.name} FL{waypoint.flight_level} {waypoint.speed}")

        return waypoint
