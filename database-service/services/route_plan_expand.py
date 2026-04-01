"""Expand Item 15 route strings into ordered waypoint name lists."""

from __future__ import annotations

from types import SimpleNamespace

from common.helpers.logging_service import LoggingService
from common.helpers.route_parser import RouteParser, preprocess_route_string
from common.helpers.route_enricher import RouteEnricher
from common.models.flight_parser.parsed_flight_plan import ParsedFlightPlan

logger = LoggingService.get_logger(__name__)


def _parsed_segment_idents(parsed: ParsedFlightPlan) -> list[str]:
    """Return waypoint identifiers from parsed legs only (no airway expansion).

    Args:
        parsed: Output of ``RouteParser.parse``.

    Returns:
        Ordered waypoint or coordinate idents from raw segments.
    """
    return [segment.ident for segment in parsed.segments]


def expand_route_to_waypoint_names(
    *,
    route_string: str | None,
    lat: float,
    lon: float,
    flight_level: int | None,
    ground_speed_kt: int | None,
) -> list[str] | None:
    """
    Parse and enrich a route string into ordered waypoint identifiers.

    Args:
        route_string: Raw Item 15 style route, or None when absent.
        lat: Aircraft latitude for fix resolution.
        lon: Aircraft longitude for fix resolution.
        flight_level: Current flight level (100s ft) or None.
        ground_speed_kt: Ground speed in knots or None before kinematics.

    Returns:
        Non-empty list of waypoint names on success, None when parsing or
        enrichment yields no usable plan.

    Raises:
        ValueError: When ``route_string`` is None or blank.
    """
    if route_string is None or not str(route_string).strip():
        raise ValueError(
            "expand_route_to_waypoint_names requires a non-empty route_string"
        )

    raw_route = str(route_string).strip()
    position = SimpleNamespace(
        lat=lat,
        lon=lon,
        flight_level=flight_level,
        ground_speed_kt=ground_speed_kt,
    )

    try:
        normalized = preprocess_route_string(raw_route)
        parser = RouteParser()
        parsed = parser.parse(normalized)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning(
            "Route parse failed, skipping row: %s",
            exc,
        )
        return None

    try:
        enricher = RouteEnricher()
        enriched = enricher.enrich(position, parsed)
        names = [segment.ident for segment in enriched.segments]
        if names:
            return names
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning(
            "Route enrich failed, trying parsed segments only: %s",
            exc,
        )

    try:
        fallback = _parsed_segment_idents(parsed)
        if fallback:
            return fallback
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Parsed segment fallback failed: %s", exc)

    logger.warning(
        "No waypoint names derived for non-empty route: %s",
        raw_route[:80],
    )
    return None
