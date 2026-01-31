"""
This module house calculations used to
recognize possible conflicts between flights
"""
import math
from typing import Protocol

import numpy as np
from numpy import array

from common.helpers.logging_service import LoggingService
from common.helpers.physics_calculator import PhysicsCalculator

logger = LoggingService.get_logger(__name__)

class FlightLike(Protocol):
    """Protocol defining the interface for flight objects used in MTCD calculations."""
    lat: float
    lon: float
    flight_level: int
    speed: int
    track_heading: int
    vertical_speed: float


class MtcdToolkit:
    """This class is responsible for MTCD evaluation"""
    def __init__(self):
        self.physics_calculator = PhysicsCalculator()

    def calculate_closest_approach_point(
        self, 
        flight_1: FlightLike,
        flight_2: FlightLike
    ) -> tuple[float, float, float, float, float, float] | None:
        """
        Calculates the closest approach point between two flights.
        
        Args:
            flight_1: Flight object with attributes: lat, lon, flight_level, speed, track_heading, vertical_speed
            flight_2: Flight object with attributes: lat, lon, flight_level, speed, track_heading, vertical_speed
            
        Returns:
            Tuple of (horizontal_distance, vertical_distance, time_to_closest_approach,
                     middle_point_lat, middle_point_lon, middle_point_fl) or None
        """
        if flight_1 is None or flight_2 is None:
            raise ValueError('Both flight objects must be provided')

        # position vector of flight 1
        # flight 1 used as reference point (NM)
        flight_1_position_vector = np.array([0, 0, 0])
        # get speed vector of flight 1 (kts)
        flight_1_speed_vector = self.get_speed_vector(
            flight_1.speed,
            flight_1.track_heading,
            flight_1.vertical_speed
        )

        # get position vector of flight 2 (NM from reference point of flight 1)
        [
            east,
            north,
            up
        ] = self.physics_calculator.get_distance_vector_enu_between_positions(
            flight_1.lat, flight_1.lon, flight_1.flight_level,
            flight_2.lat, flight_2.lon, flight_2.flight_level
        )

        flight_2_position_vector = np.array([
            self.physics_calculator.km_to_nm(east),
            self.physics_calculator.km_to_nm(north),
            self.physics_calculator.km_to_nm(up)
        ])

        # get speed vector of flight 2 (kts)
        flight_2_speed_vector = self.get_speed_vector(
            flight_2.speed,
            flight_2.track_heading,
            flight_2.vertical_speed
        )

        # get relative position (NM from reference point)
        relative_vector_pos = (
                flight_2_position_vector - flight_1_position_vector
        )

        # get relative speed flight 2 speed - flight 1 speed (kts)
        relative_vector_ground_speed = (
                flight_2_speed_vector - flight_1_speed_vector
        )

        speed_dot_product = np.dot(
            relative_vector_ground_speed, relative_vector_ground_speed
        )
        if speed_dot_product < 1e-10:
            # Aircraft have identical velocity vectors - no unique CPA exists
            logger.info(vars(flight_1))
            logger.info(vars(flight_2))
            logger.info('Aircraft have identical velocity vectors')
            return None

        # calculate time to the closest approach of flights (hours)
        time_to_closest_approach = -(
                (np.dot(relative_vector_pos, relative_vector_ground_speed))
                / speed_dot_product
        )

        if time_to_closest_approach < 0:
            # Closest point already passed
            logger.info('Closest point of approach already passed')
            return None

        # calculate distance between flights in the closest approach point (NM)
        east_distance = (
                relative_vector_pos[0]
                + relative_vector_ground_speed[0] * time_to_closest_approach
        )
        north_distance = (
                relative_vector_pos[1]
                + relative_vector_ground_speed[1] * time_to_closest_approach
        )
        up_distance = (
                relative_vector_pos[2]
                + relative_vector_ground_speed[2] * time_to_closest_approach
        )
        horizontal_distance = math.sqrt(east_distance**2 + north_distance**2)

        # calculate middle point of closest approach between flights (lat, lon)
        relative_pos_at_cpa = np.array([
            east_distance, north_distance, up_distance
        ])

        flight_1_pos_at_cpa = (
                flight_1_position_vector
                + flight_1_speed_vector * time_to_closest_approach
        )
        middle_point_global = flight_1_pos_at_cpa + 0.5 * relative_pos_at_cpa

        [
            middle_point_lat,
            middle_point_lon,
            middle_point_fl
        ] = self.physics_calculator.enu_to_latlon(
            self.physics_calculator.nm_to_km(float(middle_point_global[0])),
            self.physics_calculator.nm_to_km(float(middle_point_global[1])),
            self.physics_calculator.nm_to_km(float(middle_point_global[2])),
            flight_1.lat, flight_1.lon, flight_1.flight_level
        )

        return (
            horizontal_distance,
            float(up_distance),
            time_to_closest_approach,
            middle_point_lat,
            middle_point_lon,
            middle_point_fl
        )

    @staticmethod
    def get_speed_vector(
            ground_speed: int,
            track_heading: int,
            vertical_speed: float
    ) -> array:
        """
        Decomposes ground speed and heading into ENU components

        :param ground_speed: Ground speed of flight (kts)
        :param track_heading: Heading of flight with wind components in degrees (0° = North, clockwise)
        :param vertical_speed: Vertical speed in ft/min
        :return: np.array([east, north, up]) speed vectors in kts
        """
        heading_rad = np.deg2rad(track_heading)

        east = ground_speed * np.sin(heading_rad)  # East component
        north = ground_speed * np.cos(heading_rad)  # North component
        vertical_speed_in_kts = vertical_speed * 60 / 6076.12 # ft/min to kts

        return np.array([east, north, vertical_speed_in_kts])
