"""
This module is used for flight plan storage
"""

from ..models.waypoint import Waypoint

class FlightPlanService:
    """
    This class is responsible for flight plans which are also propagated through api into BlueSky
    """

    def __init__(self):
        self.flight_plans = {}

    def add_waypoint_to_flight_plan(self, flight_id: str, waypoint: Waypoint) -> None:
        """
        :param flight_id: ID of the flight like CSA201
        :param waypoint: Waypoint where its name is as it is in aviation map (TUMKA, ARVEG...)
        """
        if flight_id not in self.flight_plans:
            self.flight_plans[flight_id] = [waypoint]
            return

        self.flight_plans[flight_id].append(waypoint)

    def get_flight_plan(self, flight_id: str) -> list[Waypoint]:
        """
        :param flight_id: ID of the flight like CSA201
        :return: empty array when flight have no waypoints
        and array of waypoints when flight has waypoints
        """
        if flight_id not in self.flight_plans:
            return []

        return self.flight_plans[flight_id]

    def reset(self) -> None:
        """
        Deletes all currently stored flight plans
        """
        self.flight_plans = {}
