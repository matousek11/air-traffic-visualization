"""
This module houses calculations used to
recognize possible conflicts between flights
"""
import math
from typing import Any, NamedTuple

import numpy as np
from numpy import array

from common.helpers.logging_service import LoggingService
from common.helpers.physics_calculator import PhysicsCalculator
from common.models.position_3d import Position3D

logger = LoggingService.get_logger(__name__)

class FlightLike(NamedTuple):
    """Protocol defining the interface for flight objects used in MTCD calculations."""
    lat: float
    lon: float
    flight_level: int
    ground_speed: int # kts
    track_heading: int
    vertical_speed: float # ft/min

class Conflict(NamedTuple):
    """DTO for predicted conflict"""
    horizontal_distance: float # in NM
    vertical_distance: float # in NM
    time_to_conflict_entry: float # in hours
    time_to_conflict_exit: float # in hours
    time_to_closest_approach: float # in hours
    flight_1_conflict_entry_pos: Position3D
    flight_1_conflict_exit_pos: Position3D
    flight_2_conflict_entry_pos: Position3D
    flight_2_conflict_exit_pos: Position3D
    middle_point: Position3D # point between flights during CPA


class MtcdToolkit:
    """This class is responsible for MTCD evaluation"""
    def __init__(self):
        self.physics_calculator = PhysicsCalculator()

    def position_after_elapsed_hours(
            self,
            flight: FlightLike,
            elapsed_hours: float,
    ) -> Position3D:
        """Position after constant-velocity ENU motion from the current state.

        Args:
            flight: Current state (position, speed, heading, vertical_speed).
            elapsed_hours: Hours to advance.

        Returns:
            Geographic position and flight level after elapsed time.
        """
        if elapsed_hours <= 0:
            return Position3D(
                flight.lat,
                flight.lon,
                float(flight.flight_level),
            )

        origin = np.array([0.0, 0.0, 0.0])
        speed_vector = self.get_speed_vector(
            flight.ground_speed,
            flight.track_heading,
            flight.vertical_speed,
        )
        return self._calculate_pos(flight, origin, speed_vector, elapsed_hours)

    def calculate_closest_approach_point(
        self, 
        flight_1: FlightLike,
        flight_2: FlightLike
    ) -> Conflict | None:
        """
        Calculates the closest approach point between two flights.
        
        Args:
            flight_1: Flight object with attributes: lat, lon, flight_level, ground_speed, track_heading, vertical_speed
            flight_2: Flight object with attributes: lat, lon, flight_level, ground_speed, track_heading, vertical_speed
            
        Returns:
            Tuple of (horizontal_distance, vertical_distance, time_to_closest_approach,
                     middle_point_lat, middle_point_lon, middle_point_fl) or None
        """
        logger.info('Starting precise check.')
        logger.info('Flight 1 data: %s', flight_1)
        logger.info('Flight 2 data: %s', flight_2)

        if flight_1 is None or flight_2 is None:
            raise ValueError('Both flight objects must be provided')

        # position vector of flight 1
        # flight 1 used as the reference point (NM)
        flight_1_position_vector = np.array([0, 0, 0])
        # get speed vector of flight 1 (kts)
        flight_1_speed_vector = self.get_speed_vector(
            flight_1.ground_speed,
            flight_1.track_heading,
            flight_1.vertical_speed
        )

        # get the position vector of flight 2 (NM from reference point of flight 1)
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
            flight_2.ground_speed,
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
            logger.info('Aircraft have identical velocity vectors')
            return None

        # calculate time to the closest approach of flights (hours)
        time_to_closest_approach = -(
                (np.dot(relative_vector_pos, relative_vector_ground_speed))
                / speed_dot_product
        )

        if time_to_closest_approach < 0:
            # The closest point already passed
            logger.info(
                'Closest point of approach already passed, time: %d',
                time_to_closest_approach,
            )
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

        # calculate the middle point of the closest approach between flights (lat, lon)
        relative_pos_at_cpa = np.array([
            east_distance, north_distance, up_distance
        ])

        flight_1_pos_at_cpa = (
                flight_1_position_vector
                + flight_1_speed_vector * time_to_closest_approach
        )
        middle_point_global = flight_1_pos_at_cpa + 0.5 * relative_pos_at_cpa

        middle_point = self.physics_calculator.enu_to_latlon(
            self.physics_calculator.nm_to_km(float(middle_point_global[0])),
            self.physics_calculator.nm_to_km(float(middle_point_global[1])),
            self.physics_calculator.nm_to_km(float(middle_point_global[2])),
            flight_1.lat, flight_1.lon, flight_1.flight_level
        )

        result = self._calculate_entry_point_to_conflict(
            relative_vector_pos,
            relative_vector_ground_speed
        )

        if result is None:
            # flights are not going to be close enough
            logger.info('Flights are not going to be close enough in selected segments.')
            return None

        time_to_conflict_entry, time_to_conflict_exit = result

        if math.isinf(time_to_conflict_entry) or math.isinf(time_to_conflict_exit):
            raise ValueError('Conflict entry and exit times should not be infinite here')

        flight_1_conflict_entry_pos = self._calculate_pos(
            flight_1,
            flight_1_position_vector,
            flight_1_speed_vector,
            time_to_conflict_entry,
        )
        flight_1_conflict_exit_pos = self._calculate_pos(
            flight_1,
            flight_1_position_vector,
            flight_1_speed_vector,
            time_to_conflict_exit,
        )

        flight_2_conflict_entry_pos = self._calculate_pos(
            flight_1,
            flight_2_position_vector,
            flight_2_speed_vector,
            time_to_conflict_entry,
        )
        flight_2_conflict_exit_pos = self._calculate_pos(
            flight_1,
            flight_2_position_vector,
            flight_2_speed_vector,
            time_to_conflict_exit,
        )

        return Conflict(
            horizontal_distance,
            float(up_distance),
            time_to_conflict_entry,
            time_to_conflict_exit,
            float(time_to_closest_approach),
            flight_1_conflict_entry_pos,
            flight_1_conflict_exit_pos,
            flight_2_conflict_entry_pos,
            flight_2_conflict_exit_pos,
            middle_point,
        )

    def _calculate_pos(
            self,
            ref_pos: FlightLike,
            flight_position_vector: np.ndarray[tuple[Any, ...], np.dtype],
            flight_speed_vector: np.ndarray[tuple[Any, ...], np.dtype],
            remaining_time: float,
    ) -> Position3D:
        calculated_flight_pos = (
                flight_position_vector + flight_speed_vector * remaining_time
        )

        return self.physics_calculator.enu_to_latlon(
            self.physics_calculator.nm_to_km(float(calculated_flight_pos[0])),
            self.physics_calculator.nm_to_km(float(calculated_flight_pos[1])),
            self.physics_calculator.nm_to_km(float(calculated_flight_pos[2])),
            ref_pos.lat, ref_pos.lon, ref_pos.flight_level
        )

    def _calculate_entry_point_to_conflict(
            self,
            relative_vector_pos,
            relative_vector_ground_speed
    ) -> tuple[float, float] | None:
        """
        Calculates entry and exit point to conflict cylinder between two flights.

        :param relative_vector_pos: relative position in ENU
        :param relative_vector_ground_speed: relative ground speed in ENU
        :return: tuple of entry time and exit time from conflict or None if no conflict exists,
        in case that flights are already in conflict and stay in conflict infinity will be returned
        """
        HORIZONTAL_SEP_NM = 5.0 # TODO: get correct separation distance for position of CPA
        VERTICAL_SEP_NM = PhysicsCalculator.feet_to_nautical_miles(
            1000.0,
        )  # TODO: get correct separation distance for position of CPA

        # Horizontal calculation (X,Y - North, East)
        relative_pos_xy = relative_vector_pos[:2]
        relative_ground_speed_xy = relative_vector_ground_speed[:2]

        # Coefficients of quadratic equation: a*t^2 + b*t + c = 0
        a = np.dot(relative_ground_speed_xy, relative_ground_speed_xy)
        b = 2.0 * np.dot(relative_pos_xy, relative_ground_speed_xy)
        c = np.dot(relative_pos_xy, relative_pos_xy) - HORIZONTAL_SEP_NM ** 2

        if abs(a) < 1e-10:
            # Flights fly parallel and with the same speed
            if c < 0:
                # Flights are already in horizontal infinite conflict with current trajectory
                time_to_horizontal_entry, time_to_horizontal_exit = float('-inf'), float('inf')
            else:
                # Flights will not enter a conflict with the current trajectory
                return None
        else:
            discriminant = b ** 2 - 4 * a * c

            if discriminant < 0:
                return None  # flights are not going to have conflict with the current trajectory

            discriminant = max(0.0, discriminant)
            sqrt_d = math.sqrt(discriminant)
            # calculate the time of an entry and exit to a conflict
            time_to_horizontal_entry = (-b - sqrt_d) / (2 * a)
            time_to_horizontal_exit = (-b + sqrt_d) / (2 * a)

        # Vertical calculation (Z - Up)
        relative_pos_z = relative_vector_pos[2]
        relative_ground_speed_z = relative_vector_ground_speed[2]

        if abs(relative_ground_speed_z) < 1e-10:
            # Flights are maintaining the same relative altitude
            if abs(relative_pos_z) < VERTICAL_SEP_NM:
                # They are already within vertical conflict
                vertical_entry_time, vertical_exit_time = float('-inf'), float('inf')
            else:
                # Flights are safely separated forever with current trajectory
                return None
        else:
            t_v1 = (VERTICAL_SEP_NM - relative_pos_z) / relative_ground_speed_z
            t_v2 = (-VERTICAL_SEP_NM - relative_pos_z) / relative_ground_speed_z

            # Order the times correctly
            vertical_entry_time = min(t_v1, t_v2)
            vertical_exit_time = max(t_v1, t_v2)

        # --- Interval Intersection ---
        # The true conflict cylinder is breached only when BOTH separations are violated
        time_to_conflict_entry = max(time_to_horizontal_entry, vertical_entry_time)
        time_to_conflict_exit = min(time_to_horizontal_exit, vertical_exit_time)

        # Evaluate if the overlapping interval is valid and hasn't completely passed
        if time_to_conflict_entry <= time_to_conflict_exit and time_to_conflict_exit >= 0:
            return float(time_to_conflict_entry), float(time_to_conflict_exit)

        return None

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
        vertical_speed_in_kts = PhysicsCalculator.feet_per_minute_to_knots(
            vertical_speed,
        )

        return np.array([east, north, vertical_speed_in_kts])
