"""Adapter wrapping flight position rows for MTCD helpers."""

from datetime import datetime
from types import SimpleNamespace


class FlightPositionAdapter:
    """Adapter to convert FlightPosition from database to Flight-like object for MtcdToolkit."""

    def __init__(self, flight_position, flight_id: str):
        """
        Initialize adapter from FlightPosition.

        Args:
            flight_position: FlightPosition object from database
            flight_id: Flight ID
        """
        self.ts = flight_position.ts
        self.flight_id = flight_id
        self.lat = flight_position.lat
        self.lon = flight_position.lon
        self.flight_level = flight_position.flight_level if flight_position.flight_level else 0
        self.speed = flight_position.ground_speed_kt
        self.heading = flight_position.heading
        self.track_heading = flight_position.track_heading
        self.route = flight_position.route
        # vertical_speed in ft/min (same as vertical_rate_fpm)
        self.vertical_speed = float(flight_position.vertical_rate_fpm or 0)

    def copy_with(
            self,
            lat: float | None = None,
            lon: float | None = None,
            flight_level: int | None = None,
            ts: datetime | None = None,
            speed: float | None = None,
            heading: int | None = None,
            track_heading: int | None = None,
            route: str | None = None,
            vertical_speed: float | None = None,
    ) -> "FlightPositionAdapter":
        """Return a new adapter with selected fields replaced.

        Args:
            lat: New latitude or None to keep.
            lon: New longitude or None to keep.
            flight_level: New flight level or None to keep.
            ts: New timestamp or None to keep.
            speed: New ground speed (kt) or None to keep.
            heading: New heading or None to keep.
            track_heading: New track heading or None to keep.
            route: New route string or None to keep.
            vertical_speed: New vertical speed (ft/min) or None to keep.

        Returns:
            New FlightPositionAdapter instance.
        """
        new_ts = ts if ts is not None else self.ts
        new_lat = self.lat if lat is None else lat
        new_lon = self.lon if lon is None else lon
        new_fl = self.flight_level if flight_level is None else flight_level
        new_spd = self.speed if speed is None else speed
        new_hdg = self.heading if heading is None else heading
        new_trk = self.track_heading if track_heading is None else track_heading
        new_route = self.route if route is None else route
        new_vs = (
            self.vertical_speed if vertical_speed is None else vertical_speed
        )
        backing = SimpleNamespace(
            ts=new_ts,
            lat=new_lat,
            lon=new_lon,
            flight_level=new_fl,
            ground_speed_kt=new_spd,
            heading=new_hdg,
            track_heading=new_trk,
            route=new_route,
            vertical_rate_fpm=new_vs,
        )
        return FlightPositionAdapter(backing, self.flight_id)
