"""Retrieve normalized NM B2B flight records for downstream processing.

The module is intentionally split into:

- request builders for NM B2B XML payloads,
- XML parsers that normalize replies into Python dataclasses,
- a thin CLI kept only for manual testing.

Usage as CLI::

    python flights_in_airspace_data_retrieval.py \
        --airspace LK --airspace ED \
        --start-datetime "2026-03-21 09:00" \
        --end-datetime   "2026-03-21 09:20"

Usage as library::

    from datetime import datetime

    from flights_in_airspace_data_retrieval import (
        B2BConfig,
        FlightRecord,
        fetch_flights_in_airspaces,
    )

    flights: list[FlightRecord] = fetch_flights_in_airspaces(
        airspaces=["LK"],
        start_datetime=datetime(2025, 9, 7, 9, 0),
        end_datetime=datetime(2025, 9, 7, 9, 20),
        config=B2BConfig(end_user_id="myuser"),
    )

The primary data source in this iteration is
``FlightListByAirspaceRequest``. A separate
building block, but no retrieval fallback flow is implemented yet.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import xml.dom.minidom
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

import redis

log = logging.getLogger(__name__)

# NM ``sendTime`` uses second precision; ``trafficWindow`` uses minutes only.
B2B_SEND_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
B2B_TRAFFIC_WINDOW_FORMAT = "%Y-%m-%d %H:%M"
B2B_ISO_UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

B2B_TRAFFIC_TYPE = "LOAD"
B2B_CALCULATION_TYPE = "OCCUPANCY"
ROUTE_FIELD_ICAO = "icaoRoute"
ROUTE_FIELD_FILED = "filedRoute"
DEFAULT_ROUTE_FIELD = ROUTE_FIELD_ICAO
POSITION_SOURCE_FIELDS = ("lastKnownPosition", "ctfmPointProfile")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class B2BConfig:
    """Connection and protocol settings for the NM B2B Redis proxy."""

    redis_host: str = "10.15.2.203"
    redis_port: int = 6379
    end_user_id: str = "lukasm"
    channel_suffix: str = ":1"
    response_timeout_s: int = 90

    @property
    def request_channel(self) -> str:
        return f"css:b2b:req:{self.end_user_id}{self.channel_suffix}"

    @property
    def reply_channel(self) -> str:
        return f"css:b2b:rep:{self.end_user_id}{self.channel_suffix}"


@dataclass
class FlightKeys:
    """Identity fields required by ``FlightRetrievalRequest``."""

    flight_id: str
    aircraft_id: str
    aerodrome_of_departure: str | None = None
    non_icao_aerodrome_of_departure: bool = False
    air_filed: bool = False
    aerodrome_of_destination: str | None = None
    non_icao_aerodrome_of_destination: bool = False
    estimated_off_block_time: str | None = None


@dataclass
class FlightRecordCandidate:
    """Parsed flight data directly obtainable from list reply XML."""

    airspace: str
    flight_id: str
    flight_state: str | None = None
    aircraft_type: str | None = None
    origin: str | None = None
    destination: str | None = None
    time_over: str | None = None
    lat: float | None = None
    lon: float | None = None
    flight_level: int | None = None
    route_string: str | None = None
    route_source_field: str | None = None
    flight_keys: FlightKeys | None = None


@dataclass
class FlightRecord:
    """Final normalized record returned by service methods."""

    sample_time: str
    time_over: str | None
    flight_id: str
    aircraft_type: str | None
    origin: str | None
    destination: str | None
    lat: float | None
    lon: float | None
    flight_level: int | None
    route_string: str | None
    airspace: str
    flight_state: str | None = None
    route_source_field: str | None = None


class B2BError(Exception):
    """Raised when an NM B2B request/reply cycle fails."""


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _local_name(tag: str | None) -> str:
    """Return the local part of a possibly namespace-qualified XML tag."""
    if not tag:
        return ""
    return tag.split("}")[-1]


def _extract_direct_child(
    parent: ET.Element,
    local_name: str,
) -> ET.Element | None:
    """Return the first direct child with the given local XML name."""
    for child in parent:
        if _local_name(child.tag) == local_name:
            return child
    return None


def _extract_child_text(parent: ET.Element, local_name: str) -> str | None:
    """Return stripped text from the first matching direct child."""
    child = _extract_direct_child(parent, local_name)
    if child is None or child.text is None:
        return None
    text = child.text.strip()
    return text or None


def _extract_nested_text(parent: ET.Element, *path: str) -> str | None:
    """Return text from a nested direct-child path."""
    current = parent
    for local_name in path:
        child = _extract_direct_child(current, local_name)
        if child is None:
            return None
        current = child
    if current.text is None:
        return None
    text = current.text.strip()
    return text or None


def _extract_descendant_text(parent: ET.Element, local_name: str) -> str | None:
    """Return text from the first matching descendant."""
    for descendant in parent.iter():
        if _local_name(descendant.tag) != local_name:
            continue
        if descendant.text is None:
            continue
        text = descendant.text.strip()
        if text:
            return text
    return None


def _parse_bool(text: str | None, *, default: bool = False) -> bool:
    """Convert common XML boolean strings to Python bool."""
    if text is None:
        return default
    return text.strip().lower() == "true"


def _parse_float(text: str | None) -> float | None:
    """Safely parse a float from XML text."""
    if text is None:
        return None
    try:
        return float(text.strip())
    except ValueError:
        return None


def _format_now_as_iso_utc() -> str:
    """Return current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).strftime(B2B_ISO_UTC_FORMAT)


def _format_b2b_timestamp_as_iso(value: str | None) -> str | None:
    """Convert common NM B2B timestamps into ISO-8601 UTC."""
    if value is None:
        return None
    raw = value.strip()
    for fmt in (B2B_SEND_TIME_FORMAT, B2B_TRAFFIC_WINDOW_FORMAT):
        try:
            parsed = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        return parsed.replace(tzinfo=timezone.utc).strftime(B2B_ISO_UTC_FORMAT)
    return raw


def format_b2b_traffic_window(dt: datetime) -> str:
    """Format *dt* for B2B ``trafficWindow`` ``wef`` / ``unt`` (minute precision, UTC).

    Naive datetimes are formatted as-is (callers should treat them as UTC).
    Aware datetimes are converted to UTC first. Seconds are not sent.
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime(B2B_TRAFFIC_WINDOW_FORMAT)


def _build_requested_flight_fields(requested_route_field: str) -> tuple[str, ...]:
    """Return the minimal set of requested fields for this module."""
    return (
        "flightState",
        "aircraftType",
        "lastKnownPosition",
        requested_route_field,
    )


def build_flight_list_by_airspace_request_xml(
    end_user_id: str,
    wef: str,
    unt: str,
    airspace: str,
    *,
    requested_route_field: str = DEFAULT_ROUTE_FIELD,
) -> str:
    """Build a non-SOAP ``FlightListByAirspaceRequest`` XML document."""

    send_time = datetime.now(timezone.utc).strftime(B2B_SEND_TIME_FORMAT)
    fields_xml = "".join(
        f"  <requestedFlightFields>{field}</requestedFlightFields>\n"
        for field in _build_requested_flight_fields(requested_route_field)
    )
    return (
        '<?xml version="1.0"?>\n'
        '<flight:FlightListByAirspaceRequest'
        ' xmlns:flight="eurocontrol/cfmu/b2b/FlightServices">\n'
        f"  <endUserId>{end_user_id}</endUserId>\n"
        f"  <sendTime>{send_time}</sendTime>\n"
        "  <dataset>\n"
        "    <type>OPERATIONAL</type>\n"
        "  </dataset>\n"
        "  <includeProposalFlights>false</includeProposalFlights>\n"
        "  <includeForecastFlights>true</includeForecastFlights>\n"
        f"  <trafficType>{B2B_TRAFFIC_TYPE}</trafficType>\n"
        "  <trafficWindow>\n"
        f"    <wef>{wef}</wef>\n"
        f"    <unt>{unt}</unt>\n"
        "  </trafficWindow>\n"
        f"{fields_xml}"
        "  <countsInterval>\n"
        "    <duration>0001</duration>\n"
        "    <step>0001</step>\n"
        "  </countsInterval>\n"
        f"  <calculationType>{B2B_CALCULATION_TYPE}</calculationType>\n"
        f"  <airspace>{airspace}</airspace>\n"
        "</flight:FlightListByAirspaceRequest>\n"
    )


# ---------------------------------------------------------------------------
# Reply parsing helpers
# ---------------------------------------------------------------------------

def _parse_reply_status(xml_str: str) -> bool:
    """Return ``True`` if the reply ``<status>`` element reads ``OK``."""
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return False
    for el in root.iter():
        if _local_name(el.tag) == "status" and el.text and el.text.strip().upper() == "OK":
            return True
    return False


# ---------------------------------------------------------------------------
# Redis request / reply cycle
# ---------------------------------------------------------------------------

def _decode(data: bytes | str) -> str:
    """Ensure *data* is a ``str``."""
    return data.decode("utf-8") if isinstance(data, bytes) else data


def _publish_request_and_receive_payload(
    redis_client: redis.Redis,
    pubsub: redis.client.PubSub,
    request_xml: str,
    config: B2BConfig,
) -> str:
    """Publish XML request and return the raw XML reply payload."""
    req_bytes = request_xml.encode("utf-8")
    log.info(
        "Publishing request (%d bytes) to %s.",
        len(req_bytes),
        config.request_channel,
    )
    n_subs = redis_client.publish(config.request_channel, req_bytes)
    log.debug("publish() returned subscriber count=%s.", n_subs)
    log.info("Waiting for B2B reply...")
    return receive_payload(pubsub, config)


def receive_payload(
    p: redis.client.PubSub,
    config: B2BConfig,
) -> str:
    """Wait for the synchronous ``FlightListByAirspaceReply`` on the channel.

    Always returns a decoded ``str``.

    Raises :class:`B2BError` on timeout or empty response.
    """
    log.info(
        "Listening for reply on channel (timeout=%ss)...",
        config.response_timeout_s,
    )
    msg = p.get_message(timeout=config.response_timeout_s)
    if msg is None:
        log.error("get_message returned None (timeout).")
        raise B2BError(
            f"No reply received within {config.response_timeout_s}s."
        )
    log.debug(
        "Redis pub/sub message: type=%s data_present=%s",
        msg.get("type"),
        bool(msg.get("data")),
    )
    if not msg.get("data"):
        log.error("Message had no data payload: %s", msg)
        raise B2BError(
            f"No reply received within {config.response_timeout_s}s."
        )

    payload = _decode(msg["data"])
    log.info("Reply received: %d character(s).", len(payload))
    log.debug("Reply prefix: %s", payload[:500] if len(payload) > 500 else payload)
    return payload


# ---------------------------------------------------------------------------
# Flight list reply parsing
# ---------------------------------------------------------------------------

def _flight_level_to_fl(unit: str | None, level_text: str | None) -> int | None:
    """Convert NM flight level representation to integer FL value."""
    if not level_text:
        return None
    raw = level_text.strip()
    if not raw.isdigit():
        return None
    level = int(raw)
    if unit and unit.strip().upper() == "A":
        return level
    if level >= 1000:
        return level // 100
    return level


def _parse_flight_keys(
    flight_id_el: ET.Element,
    flight_id: str,
) -> FlightKeys | None:
    """Extract ``flightId.keys`` block if it is present."""
    keys_el = _extract_direct_child(flight_id_el, "keys")
    if keys_el is None:
        return None
    aircraft_id = _extract_child_text(keys_el, "aircraftId") or flight_id
    return FlightKeys(
        flight_id=flight_id,
        aircraft_id=aircraft_id,
        aerodrome_of_departure=_extract_child_text(
            keys_el,
            "aerodromeOfDeparture",
        ),
        non_icao_aerodrome_of_departure=_parse_bool(
            _extract_child_text(keys_el, "nonICAOAerodromeOfDeparture")
        ),
        air_filed=_parse_bool(_extract_child_text(keys_el, "airFiled")),
        aerodrome_of_destination=_extract_child_text(
            keys_el,
            "aerodromeOfDestination",
        ),
        non_icao_aerodrome_of_destination=_parse_bool(
            _extract_child_text(keys_el, "nonICAOAerodromeOfDestination")
        ),
        estimated_off_block_time=_extract_child_text(
            keys_el,
            "estimatedOffBlockTime",
        ),
    )


def _extract_route(
    flight_el: ET.Element,
    requested_route_field: str,
) -> tuple[str | None, str | None]:
    """Return route string and source field name."""
    for field in (requested_route_field, ROUTE_FIELD_FILED, ROUTE_FIELD_ICAO):
        route = _extract_child_text(flight_el, field)
        if route:
            return route, field
    return None, None


def _extract_position_source(
    flight_el: ET.Element,
) -> tuple[ET.Element | None, str | None]:
    """Return the first available position-like source block."""
    for field in POSITION_SOURCE_FIELDS:
        source = _extract_direct_child(flight_el, field)
        if source is not None:
            return source, field
    return None, None


def _extract_lat_lon(position_el: ET.Element | None) -> tuple[float | None, float | None]:
    """Extract latitude and longitude from a position block if available."""
    if position_el is None:
        return None, None

    lat_text = (
        _extract_nested_text(position_el, "point", "position", "latitude")
        or _extract_nested_text(position_el, "position", "latitude")
        or _extract_child_text(position_el, "latitude")
        or _extract_descendant_text(position_el, "latitude")
    )
    lon_text = (
        _extract_nested_text(position_el, "point", "position", "longitude")
        or _extract_nested_text(position_el, "position", "longitude")
        or _extract_child_text(position_el, "longitude")
        or _extract_descendant_text(position_el, "longitude")
    )

    lat = _parse_float(lat_text)
    lon = _parse_float(lon_text)
    if lat is not None and lon is not None:
        return lat, lon

    pos_text = _extract_descendant_text(position_el, "pos")
    if pos_text:
        parts = pos_text.replace(",", " ").split()
        if len(parts) >= 2:
            lat = _parse_float(parts[0])
            lon = _parse_float(parts[1])
            if lat is not None and lon is not None:
                return lat, lon

    coordinates_text = _extract_descendant_text(position_el, "coordinates")
    if coordinates_text:
        parts = coordinates_text.replace(",", " ").split()
        if len(parts) >= 2:
            lat = _parse_float(parts[0])
            lon = _parse_float(parts[1])
            if lat is not None and lon is not None:
                return lat, lon

    return None, None


def _extract_flight_level(
    source_el: ET.Element | None,
) -> tuple[int | None, str | None]:
    """Extract numeric FL from position-like element.

    Returns:
        Tuple of parsed flight level and optional rejection reason. When
        ``ground`` or ``ceiling`` is explicitly set, the record should be
        skipped by the caller.
    """
    if source_el is None:
        return None, None

    level_el = _extract_direct_child(source_el, "flightLevel")
    if level_el is not None:
        return _flight_level_to_fl(
            _extract_child_text(level_el, "unit"),
            _extract_child_text(level_el, "level"),
        ), None

    # FourDPosition.level in the NM EEM is an optional FlightLevel object.
    level_container = _extract_direct_child(source_el, "level")
    if level_container is not None:
        if _parse_bool(_extract_child_text(level_container, "ground")):
            return None, "ground"
        if _parse_bool(_extract_child_text(level_container, "ceiling")):
            return None, "ceiling"

        nested_level = _extract_child_text(level_container, "level")
        if nested_level is not None:
            return _flight_level_to_fl(
                _extract_child_text(level_container, "unit"),
                nested_level,
            ), None
        if level_container.text and level_container.text.strip():
            return _flight_level_to_fl(None, level_container.text), None

    return None, None


def _parse_flight_candidate(
    flight_el: ET.Element,
    airspace: str,
    requested_route_field: str,
) -> FlightRecordCandidate | None:
    """Convert one ``<flight>`` node into a normalized candidate."""
    flight_id_el = _extract_direct_child(flight_el, "flightId")
    if flight_id_el is None:
        return None

    flight_id = _extract_child_text(flight_id_el, "id")
    if not flight_id:
        return None

    keys = _parse_flight_keys(flight_id_el, flight_id)
    source_el, _ = _extract_position_source(flight_el)
    position_el = None
    if source_el is not None:
        position_el = _extract_direct_child(source_el, "position")

    lat, lon = _extract_lat_lon(position_el)
    flight_level, rejection_reason = _extract_flight_level(source_el)
    route_string, route_source_field = _extract_route(
        flight_el,
        requested_route_field,
    )
    flight_state = _extract_child_text(flight_el, "flightState")

    if rejection_reason is not None:
        log.warning(
            "Skipping flight_id=%s in airspace=%s because flight level "
            "contains %s=true.",
            flight_id,
            airspace,
            rejection_reason,
        )
        return None

    if lat is None or lon is None:
        log.warning(
            "Skipping flight_id=%s in airspace=%s because position has no "
            "usable latitude/longitude.",
            flight_id,
            airspace,
        )
        return None

    return FlightRecordCandidate(
        airspace=airspace,
        flight_id=flight_id,
        flight_state=flight_state,
        aircraft_type=_extract_child_text(flight_el, "aircraftType"),
        origin=(
            keys.aerodrome_of_departure
            if keys is not None
            else _extract_descendant_text(flight_id_el, "aerodromeOfDeparture")
        ),
        destination=(
            keys.aerodrome_of_destination
            if keys is not None
            else _extract_descendant_text(flight_id_el, "aerodromeOfDestination")
        ),
        time_over=_format_b2b_timestamp_as_iso(
            _extract_child_text(source_el, "timeOver") if source_el else None
        ),
        lat=lat,
        lon=lon,
        flight_level=flight_level,
        route_string=route_string,
        route_source_field=route_source_field,
        flight_keys=keys,
    )


def parse_flights_from_reply(
    xml_payload: str,
    airspace: str,
    *,
    requested_route_field: str = DEFAULT_ROUTE_FIELD,
) -> list[FlightRecordCandidate]:
    """Parse a ``FlightListByAirspaceReply`` into a flat list of flights.

    Only ``<flight>`` elements are considered; ``<flightPlan>`` siblings
    inside ``<flights>`` wrappers are skipped.
    """
    root = ET.fromstring(xml_payload)
    flights: list[FlightRecordCandidate] = []

    for el in root.iter():
        if _local_name(el.tag) != "flight":
            continue

        candidate = _parse_flight_candidate(
            el,
            airspace,
            requested_route_field,
        )
        if candidate is None:
            continue
        flights.append(candidate)

    log.debug(
        "parse_flights_from_reply: found %d <flight> element(s).",
        len(flights),
    )
    return flights


# ---------------------------------------------------------------------------
# Debug pretty-printer
# ---------------------------------------------------------------------------

def _pretty_print_response(
    xml_payload: str,
    *,
    max_flights: int = 5,
) -> None:
    """Pretty-print the raw XML to stderr, keeping only first N flights."""
    try:
        doc = xml.dom.minidom.parseString(xml_payload)
        for node in list(doc.getElementsByTagName("flights"))[max_flights:]:
            node.parentNode.removeChild(node)
        print(doc.toprettyxml(indent="  "), file=sys.stderr)
    except Exception:
        print(xml_payload[:2000], file=sys.stderr)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def complete_flight_record(
    candidate: FlightRecordCandidate,
    *,
    sample_time: str | None = None,
) -> FlightRecord:
    """Convert parsed candidate into final normalized record."""
    return FlightRecord(
        sample_time=sample_time or _format_now_as_iso_utc(),
        time_over=candidate.time_over,
        flight_id=candidate.flight_id,
        aircraft_type=candidate.aircraft_type,
        origin=candidate.origin,
        destination=candidate.destination,
        lat=candidate.lat,
        lon=candidate.lon,
        flight_level=candidate.flight_level,
        route_string=candidate.route_string,
        airspace=candidate.airspace,
        flight_state=candidate.flight_state,
        route_source_field=candidate.route_source_field,
    )


def _validate_window(start: datetime, end: datetime) -> None:
    """Raise if the time window is invalid."""
    if start > end:
        raise ValueError(
            f"start_datetime ({start}) must not be after end_datetime ({end})."
        )
    now = datetime.now(timezone.utc)
    start_aware = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    if start_aware > now + timedelta(seconds=60):
        raise ValueError(
            f"start_datetime ({start}) appears to be in the future (now={now:%H:%M:%S} UTC)."
        )
    log.debug(
        "Time window validated: start=%s end=%s (now_utc=%s).",
        start, end, now.strftime(B2B_SEND_TIME_FORMAT),
    )


def fetch_flight_candidates_in_airspace(
    airspace: str,
    start_datetime: datetime,
    end_datetime: datetime,
    *,
    config: B2BConfig | None = None,
    print_response: bool = False,
    max_print_flights: int = 5,
    requested_route_field: str = DEFAULT_ROUTE_FIELD,
) -> list[FlightRecordCandidate]:
    """Return parsed candidates for a single airspace request."""
    _validate_window(start_datetime, end_datetime)
    active_config = config or B2BConfig()
    wef = format_b2b_traffic_window(start_datetime)
    unt = format_b2b_traffic_window(end_datetime)

    log.info(
        "Starting NM B2B flight list for airspace=%s, window %s .. %s (UTC).",
        airspace,
        wef,
        unt,
    )
    log.debug(
        "Config: redis=%s:%s request_channel=%s reply_channel=%s "
        "response_timeout_s=%s route_field=%s",
        active_config.redis_host,
        active_config.redis_port,
        active_config.request_channel,
        active_config.reply_channel,
        active_config.response_timeout_s,
        requested_route_field,
    )

    request_xml = build_flight_list_by_airspace_request_xml(
        active_config.end_user_id,
        wef,
        unt,
        airspace,
        requested_route_field=requested_route_field,
    )

    log.info(
        "Connecting to Redis at %s:%s.",
        active_config.redis_host,
        active_config.redis_port,
    )
    redis_client = redis.Redis(
        host=active_config.redis_host,
        port=active_config.redis_port,
    )
    pubsub = redis_client.pubsub()
    log.info("Subscribing to reply channel: %s", active_config.reply_channel)
    pubsub.subscribe(active_config.reply_channel)
    sub_ack = pubsub.get_message(timeout=0.5)
    if sub_ack:
        log.debug(
            "Subscription handshake: type=%s channel=%s",
            sub_ack.get("type"),
            sub_ack.get("channel"),
        )

    try:
        payload = _publish_request_and_receive_payload(
            redis_client,
            pubsub,
            request_xml,
            active_config,
        )
    finally:
        log.info("Unsubscribing and closing Redis pub/sub.")
        pubsub.unsubscribe()
        pubsub.close()

    if print_response:
        log.info("Raw response for airspace=%s (%d chars):", airspace, len(payload))
        _pretty_print_response(payload, max_flights=max_print_flights)

    if not _parse_reply_status(payload):
        log.warning("Reply status for airspace=%s was not OK.", airspace)
    else:
        log.info("Reply XML status OK for airspace=%s.", airspace)

    try:
        return parse_flights_from_reply(
            payload,
            airspace,
            requested_route_field=requested_route_field,
        )
    except ET.ParseError as exc:
        raise B2BError(
            f"Cannot parse FlightListByAirspaceReply XML for "
            f"airspace={airspace}: {exc}"
        ) from exc


def fetch_flight_records_in_airspaces(
    airspaces: Sequence[str],
    start_datetime: datetime,
    end_datetime: datetime,
    *,
    config: B2BConfig | None = None,
    print_response: bool = False,
    max_print_flights: int = 5,
    requested_route_field: str = DEFAULT_ROUTE_FIELD,
) -> list[FlightRecord]:
    """Return normalized flight records across one or more airspaces."""
    _validate_window(start_datetime, end_datetime)
    active_config = config or B2BConfig()
    sample_time = _format_now_as_iso_utc()
    n_spaces = len(airspaces)

    log.info(
        "Starting NM B2B flight list: %d airspace(s), window %s .. %s (UTC), "
        "end_user_id=%s.",
        n_spaces,
        format_b2b_traffic_window(start_datetime),
        format_b2b_traffic_window(end_datetime),
        active_config.end_user_id,
    )

    all_records: list[FlightRecord] = []
    seen_ids: set[str] = set()

    for idx, airspace in enumerate(airspaces, start=1):
        log.info(
            "[%d/%d] Fetching complete flight records for airspace=%s.",
            idx,
            n_spaces,
            airspace,
        )
        try:
            candidates = fetch_flight_candidates_in_airspace(
                airspace,
                start_datetime,
                end_datetime,
                config=active_config,
                print_response=print_response,
                max_print_flights=max_print_flights,
                requested_route_field=requested_route_field,
            )
        except B2BError:
            log.error("Failed to fetch flight candidates for airspace=%s.", airspace)
            raise

        new_unique = 0
        for candidate in candidates:
            if candidate.flight_id not in seen_ids:
                seen_ids.add(candidate.flight_id)
                all_records.append(
                    complete_flight_record(candidate, sample_time=sample_time)
                )
                new_unique += 1
            else:
                log.debug(
                    "Skipping duplicate flight_id=%s (already seen).",
                    candidate.flight_id,
                )

        log.info(
            "Airspace %s: parsed %d <flight> row(s), %d new unique "
            "(%d unique across all airspaces so far).",
            airspace,
            len(candidates),
            new_unique,
            len(all_records),
        )

    log.info(
        "Finished: %d unique flight(s) across %d airspace(s).",
        len(all_records),
        n_spaces,
    )
    return all_records


def fetch_flights_in_airspaces(
    airspaces: Sequence[str],
    start_datetime: datetime,
    end_datetime: datetime,
    *,
    config: B2BConfig | None = None,
    print_response: bool = False,
    max_print_flights: int = 5,
    requested_route_field: str = DEFAULT_ROUTE_FIELD,
) -> list[FlightRecord]:
    """Backward-compatible wrapper returning normalized flight records."""
    return fetch_flight_records_in_airspaces(
        airspaces,
        start_datetime,
        end_datetime,
        config=config,
        print_response=print_response,
        max_print_flights=max_print_flights,
        requested_route_field=requested_route_field,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_datetime_arg(value: str) -> datetime:
    """Parse CLI datetime for the traffic window (``wef``/``unt`` are minute-only in XML)."""
    value = value.strip()
    for fmt in (B2B_TRAFFIC_WINDOW_FORMAT, B2B_SEND_TIME_FORMAT):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"Invalid datetime {value!r}; expected {B2B_TRAFFIC_WINDOW_FORMAT} "
        f"or {B2B_SEND_TIME_FORMAT}"
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point for standalone execution."""
    parser = argparse.ArgumentParser(
        description=(
            "Retrieve flights occupying given airspace(s) within a time "
            "window via NM B2B (Redis pub/sub proxy)."
        ),
    )
    parser.add_argument(
        "--airspace",
        action="append",
        required=True,
        help="Airspace identifier (repeatable, e.g. --airspace LK --airspace ED).",
    )
    parser.add_argument(
        "--start-datetime",
        type=_parse_datetime_arg,
        required=True,
        help=(
            "Start of the traffic window in UTC. Primary: YYYY-MM-DD HH:MM "
            f"(maps to NM wef). Optional: {B2B_SEND_TIME_FORMAT} (seconds ignored for wef/unt)."
        ),
    )
    parser.add_argument(
        "--end-datetime",
        type=_parse_datetime_arg,
        required=True,
        help=(
            "End of the traffic window in UTC. Primary: YYYY-MM-DD HH:MM "
            f"(maps to NM unt). Optional: {B2B_SEND_TIME_FORMAT} (seconds ignored for wef/unt)."
        ),
    )
    parser.add_argument(
        "--redis-host",
        default="10.15.2.203",
        help="Redis proxy host (default: %(default)s).",
    )
    parser.add_argument(
        "--redis-port",
        type=int,
        default=6379,
        help="Redis proxy port (default: %(default)s).",
    )
    parser.add_argument(
        "--end-user-id",
        default="lukasm",
        help="NM B2B end-user identifier (default: %(default)s).",
    )
    parser.add_argument(
        "--route-field",
        choices=(ROUTE_FIELD_ICAO, ROUTE_FIELD_FILED),
        default=DEFAULT_ROUTE_FIELD,
        help=(
            "Requested route field name. Defaults to %(default)s; "
            "switch to filedRoute if live data does not expose icaoRoute."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )
    parser.add_argument(
        "--show-response",
        action="store_true",
        help="Pretty-print the raw B2B XML response to stderr.",
    )
    parser.add_argument(
        "--max-print-flights",
        type=int,
        default=5,
        help=(
            "Maximum number of flights to print in CLI output and raw XML "
            "preview (default: %(default)s)."
        ),
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    config = B2BConfig(
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        end_user_id=args.end_user_id,
    )

    try:
        log.info("CLI: invoking fetch_flight_records_in_airspaces.")
        flights = fetch_flight_records_in_airspaces(
            airspaces=args.airspace,
            start_datetime=args.start_datetime,
            end_datetime=args.end_datetime,
            config=config,
            print_response=args.show_response,
            max_print_flights=args.max_print_flights,
            requested_route_field=args.route_field,
        )
    except (B2BError, ValueError) as exc:
        log.error("%s", exc)
        return 1

    log.info("Printing normalized flight records to stdout (%d row(s)).", len(flights))
    print(
        json.dumps(
            [asdict(flight) for flight in flights[: args.max_print_flights]],
            indent=2,
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
