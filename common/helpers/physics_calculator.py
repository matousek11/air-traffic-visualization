"""
Module provides physical calculation methods to infer necessary physical quantities of plane
from two points in time
"""
import math

from common.models.position import Position


class PhysicsCalculator:
    """
    Class provides physical calculation methods to infer necessary physical quantities of plane
    from two points in time
    """
    @staticmethod
    def get_distance_between_positions(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculates distance on Earth between two points in geographic coordinate system

        :return: distance between two points in kilometers
        """
        radius_of_earth_in_km = 6371  # Radius of Earth in kilometers (haversine method)

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return radius_of_earth_in_km * c  # in kilometers

    @staticmethod
    def get_horizontal_speed(current_position: Position, previous_position: Position) -> float:
        """
        Calculates speed between two points in geographic coordinate system

        :return: speed in kilometers per hour
        """
        distance_in_km = PhysicsCalculator.get_distance_between_positions(
            current_position.lat,
            current_position.lon,
            previous_position.lat,
            previous_position.lon
        )

        hours_time_diff = (current_position.timestamp - previous_position.timestamp) / 60 * 60
        speed_in_kmh = distance_in_km / hours_time_diff
        return abs(speed_in_kmh)

    @staticmethod
    def get_vertical_speed(current_position: Position, previous_position: Position) -> float:
        """
        Calculates vertical speed between two points in geographic coordinate system

        :return: vertical speed in meters per minute
        """
        # 240 -> 24 000 feet
        # 1 feet -> 0.3048m
        feet_to_meters = 0.3048
        minute_diff = (current_position.timestamp - previous_position.timestamp) / 60
        vertical_difference = previous_position.flight_level - current_position.flight_level
        vertical_difference *= 100 * feet_to_meters
        return vertical_difference / minute_diff

    #@staticmethod
    #def get_heading():
