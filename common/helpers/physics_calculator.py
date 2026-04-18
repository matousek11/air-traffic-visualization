"""
Module provides physical calculation methods to infer
necessary physical quantities of plane from two points in time
"""
import math
from typing import Tuple

from common.models.position import Position
from common.models.position_3d import Position3D


class PhysicsCalculator:
    """
    Class provides physical calculation methods to infer
    necessary physical quantities of plane from two points in time
    """

    EARTH_RADIUS_KM = 6371.0 # Radius of Earth in kilometers (haversine method)

    # International foot (exactly 0.3048 m)
    FEET_TO_METERS = 0.3048

    # International nautical mile (exactly 1852 m)
    METERS_PER_NAUTICAL_MILE = 1852.0

    @staticmethod
    def feet_to_meters(value: float) -> float:
        """Convert a length in feet to meters.

        Args:
            value: Distance or altitude difference in feet.

        Returns:
            Equivalent length in meters.
        """
        return value * PhysicsCalculator.FEET_TO_METERS

    @staticmethod
    def meters_to_feet(value: float) -> float:
        """Convert a length in meters to feet.

        Args:
            value: Distance or altitude in meters.

        Returns:
            Equivalent in feet.
        """
        return value / PhysicsCalculator.FEET_TO_METERS

    @staticmethod
    def feet_to_nautical_miles(value: float) -> float:
        """Convert a distance in feet to nautical miles.

        Args:
            value: Distance in feet.

        Returns:
            Equivalent distance in international nautical miles.
        """
        return PhysicsCalculator.feet_to_meters(value) / (
            PhysicsCalculator.METERS_PER_NAUTICAL_MILE
        )

    @staticmethod
    def feet_per_nautical_mile() -> float:
        """Return the length of one international nautical mile in feet.

        Returns:
            One NM expressed in feet (~6076.12).
        """
        return PhysicsCalculator.meters_to_feet(
            PhysicsCalculator.METERS_PER_NAUTICAL_MILE,
        )

    @staticmethod
    def meters_per_second_to_feet_per_minute(value: float) -> float:
        """Convert vertical speed from meters per second to feet per minute.

        Args:
            value: Vertical speed in m/s.

        Returns:
            Vertical speed in ft/min.
        """
        return PhysicsCalculator.meters_to_feet(value) * 60.0

    @staticmethod
    def feet_per_minute_to_knots(value: float) -> float:
        """Convert vertical speed from feet per minute to knots (NM/h).

        Args:
            value: Vertical speed in ft/min.

        Returns:
            Equivalent speed in knots.
        """
        return (value * 60.0) / PhysicsCalculator.feet_per_nautical_mile()

    @staticmethod
    def kilometers_per_flight_level() -> float:
        """Return altitude change per one flight level in kilometers (100 ft).

        Returns:
            Kilometers corresponding to 100 ft.
        """
        return PhysicsCalculator.feet_to_meters(100) / 1000.0

    @staticmethod
    def get_distance_between_positions(
            lat1: float,
            lon1: float,
            lat2: float,
            lon2: float,
    ) -> float:
        """
        Calculates distance on Earth between
        two points in geographic coordinate system

        :return: distance between two points in kilometers
        """
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = (
                math.sin(dphi / 2) ** 2
                + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return PhysicsCalculator.EARTH_RADIUS_KM * c  # in kilometers

    def calculate_heading(
            self,
            lat1: float,
            lon1: float,
            lat2: float,
            lon2: float,
    ) -> float:
        """
        Calculates heading from point 1 to point 2 on earth
        """
        phi1, lambda1 = math.radians(lat1), math.radians(lon1)
        phi2, lambda2 = math.radians(lat2), math.radians(lon2)

        delta_lambda = lambda2 - lambda1

        y = math.sin(delta_lambda) * math.cos(phi2)
        x = (math.cos(phi1) * math.sin(phi2) -
             math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda))

        bearing = math.atan2(y, x)

        return (math.degrees(bearing) + 360) % 360

    @staticmethod
    def get_horizontal_speed(
            current_position: Position,
            previous_position: Position
    ) -> float:
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

        # normalize
        hours_time_diff = (
                (current_position.timestamp - previous_position.timestamp)
                / (60 * 60)
        )
        speed_in_kmh = distance_in_km / hours_time_diff
        return abs(speed_in_kmh)

    @staticmethod
    def get_vertical_speed(
            current_position: Position,
            previous_position: Position
    ) -> float:
        """
        Calculates vertical speed between
        two points in geographic coordinate system.

        :return: vertical speed in meters per minute (positive climb, negative descent)
        """
        minute_diff = (
                (current_position.timestamp - previous_position.timestamp) / 60
        )
        vertical_delta_feet = (
                (current_position.flight_level - previous_position.flight_level)
                * 100
        )
        vertical_delta_feet = PhysicsCalculator.feet_to_meters(vertical_delta_feet)
        return vertical_delta_feet / minute_diff

    @staticmethod
    def latlon_to_ecef(
            lat: float,
            lon: float,
            flight_level: int
    ) -> Tuple[float, float, float]:
        """Converts lat lon system to earth-centered earth-fixed system"""
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)

        radius = (
            PhysicsCalculator.EARTH_RADIUS_KM
            + flight_level * PhysicsCalculator.kilometers_per_flight_level()
        )

        x = radius * math.cos(lat_rad) * math.cos(lon_rad)
        y = radius * math.cos(lat_rad) * math.sin(lon_rad)
        z = radius * math.sin(lat_rad)

        return x, y, z

    @staticmethod
    def ecef_to_enu(
            dx: float,
            dy: float,
            dz: float,
            ref_lat: float,
            ref_lon: float,
    ) -> Tuple[float, float, float]:
        """
        Converts ECEF difference vector to local ENU coordinates.

        All distances are in kilometers.
        """
        lat = math.radians(ref_lat)
        lon = math.radians(ref_lon)

        sin_lat = math.sin(lat)
        cos_lat = math.cos(lat)
        sin_lon = math.sin(lon)
        cos_lon = math.cos(lon)

        east = -sin_lon * dx + cos_lon * dy
        north = -sin_lat * cos_lon * dx - sin_lat * sin_lon * dy + cos_lat * dz
        up = cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz

        return east, north, up

    @staticmethod
    def get_distance_vector_enu_between_positions(
            lat1: float,
            lon1: float,
            flight_level_1: int,
            lat2: float,
            lon2: float,
            flight_level_2: int,
    ) -> tuple[float, float, float]:
        """
        Returns distance vector from position 1 to position 2
        in local ENU coordinate system centered at position 1.

        :return: (east, north, up) in kilometers
        """
        x1, y1, z1 = PhysicsCalculator.latlon_to_ecef(
            lat1,
            lon1,
            flight_level_1
        )
        x2, y2, z2 = PhysicsCalculator.latlon_to_ecef(
            lat2,
            lon2,
            flight_level_2
        )

        dx = x2 - x1
        dy = y2 - y1
        dz = z2 - z1

        east, north, up = PhysicsCalculator.ecef_to_enu(dx, dy, dz, lat1, lon1)
        sagitta = (east ** 2 + north ** 2) / (2.0 * PhysicsCalculator.EARTH_RADIUS_KM)
        return east, north, up + sagitta

    @staticmethod
    def enu_to_latlon(
            east: float,
            north: float,
            up: float,
            ref_lat: float,
            ref_lon: float,
            ref_fl: int,
    ) -> Position3D:
        """
        Converts ENU coordinates to geodetic coordinates with flight level

        :param east: East offset from reference point (km)
        :param north: North offset from reference point (km)
        :param up: Up offset from reference point (km)
        :param ref_lat: Reference latitude in degrees
        :param ref_lon: Reference longitude in degrees
        :param ref_fl: Reference flight level
        """
        dlat = (
                north / PhysicsCalculator.EARTH_RADIUS_KM
        )
        dlon = (
                east / (
                        PhysicsCalculator.EARTH_RADIUS_KM
                        * math.cos(math.radians(ref_lat))
                )
        )

        lat = ref_lat + math.degrees(dlat)
        lon = ref_lon + math.degrees(dlon)
        fl = ref_fl + up / PhysicsCalculator.kilometers_per_flight_level()

        return Position3D(lat, lon, fl)

    @staticmethod
    def km_to_nm(value: float) -> float:
        """Converts km to nautical miles"""
        return value / 1.852

    @staticmethod
    def nm_to_km(value: float) -> float:
        """Converts nautical miles to kilometers"""
        return value * 1.852

    #@staticmethod
    #def get_heading():
