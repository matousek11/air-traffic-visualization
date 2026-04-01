"""Flight detail responses from database rows."""

from sqlalchemy.orm import Session

from common.helpers.logging_service import LoggingService
from models import Flight, FlightPosition
from models.flight_detail_api import FlightDetailResponse, Wind
from repositories.flight_snapshot_repository import FlightSnapshotRepository

logger = LoggingService.get_logger(__name__)


def _altitude_feet(flight_level: int | None) -> int:
    """Convert flight level (100s of feet) to altitude in feet."""
    if flight_level is None:
        return 0
    return int(flight_level) * 100


def _wind_from_position(position: FlightPosition) -> Wind:
    """
    Build Wind DTO from stored columns.

    Args:
        position: Latest flight position row.

    Returns:
        Wind model for API JSON.
    """
    lat = position.lat
    lon = position.lon
    alt_ft = _altitude_feet(position.flight_level)

    if position.wind_heading is not None and position.wind_speed is not None:
        w_lat = position.wind_lat if position.wind_lat is not None else lat
        w_lon = position.wind_lon if position.wind_lon is not None else lon
        w_alt = (
            position.wind_altitude
            if position.wind_altitude is not None
            else alt_ft
        )
        return Wind(
            heading=float(position.wind_heading),
            speed=float(position.wind_speed),
            lat=float(w_lat),
            lon=float(w_lon),
            altitude=int(w_alt),
        )

    return Wind(
        heading=0.0,
        speed=0.0,
        lat=float(lat),
        lon=float(lon),
        altitude=alt_ft,
    )


def _flight_plan_names_from_position(position: FlightPosition) -> list[str]:
    """
    Deserialize stored JSON into waypoint name strings.

    Args:
        position: Flight position row with optional flight_plan_json.

    Returns:
        Ordered waypoint identifiers for the API.
    """
    raw = position.flight_plan_json
    if raw is None:
        return []
    if not isinstance(raw, list):
        logger.warning(
            "flight_plan_json is not a list for flight %s",
            position.flight_id,
        )
        return []
    result: list[str] = []
    for item in raw:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                result.append(stripped)
            continue
        if isinstance(item, dict):
            name = item.get("name")
            if name is not None and str(name).strip():
                result.append(str(name).strip())
            continue
        logger.warning(
            "Skipping unsupported flight_plan_json entry for %s",
            position.flight_id,
        )
    return result


def _to_detail_response(
    position: FlightPosition,
    flight: Flight,
) -> FlightDetailResponse:
    """
    Map ORM rows to FlightDetailResponse.

    Args:
        position: Latest FlightPosition for the flight.
        flight: Flight row.

    Returns:
        FlightDetailResponse for JSON serialization.
    """
    plane_type = (
        flight.aircraft_type
        if flight.aircraft_type is not None
        else ""
    )
    return FlightDetailResponse(
        flight_id=position.flight_id,
        plane_type=plane_type,
        lat=float(position.lat),
        lon=float(position.lon),
        heading=int(position.heading),
        flight_level=int(position.flight_level),
        target_flight_level=position.target_flight_level,
        speed=int(position.ground_speed_kt),
        vertical_speed=float(position.vertical_rate_fpm),
        flight_plan=_flight_plan_names_from_position(position),
        route_string=position.route,
        wind=_wind_from_position(position),
        track_heading=int(position.track_heading),
    )


class FlightSnapshotService:
    """Service for listing flight details from the latest stored positions."""

    def __init__(self) -> None:
        """Initialize service with the default repository."""
        self._repository = FlightSnapshotRepository()

    def list_flight_details(self, db: Session) -> list[FlightDetailResponse]:
        """
        List all active flights with their latest position as API DTOs.

        Args:
            db: Database session.

        Returns:
            List of flight detail responses, sorted by flight_id.
        """
        rows = self._repository.list_latest_positions_with_flights(db)
        return [_to_detail_response(pos, fl) for pos, fl in rows]

    def get_flight_detail(
        self,
        db: Session,
        flight_id: str,
    ) -> FlightDetailResponse | None:
        """
        Return one flight detail or None if not found.

        Args:
            db: Database session.
            flight_id: Requested flight id.

        Returns:
            FlightDetailResponse if active flight with positions exists.
        """
        row = self._repository.get_latest_position_with_flight(db, flight_id)
        if row is None:
            return None
        position, flight = row
        return _to_detail_response(position, flight)
