"""Import NM B2B BASELINE XML files into airport, fix, nav and airway tables."""

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from typing import Any, Generator

# Ensure project root and database-service are on a path (run from project root).
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..", "..", ".."))
_DB_SERVICE = os.path.join(_REPO_ROOT, "database-service")
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
if _DB_SERVICE not in sys.path:
    sys.path.insert(0, _DB_SERVICE)

# Load .env from a database-service when running from the project root.
_ENV_PATH = os.path.join(_DB_SERVICE, ".env")
if os.path.isfile(_ENV_PATH):
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH, override=False)

# pylint: disable=wrong-import-position
from common.helpers.logging_service import LoggingService
from geoalchemy2 import WKTElement
from sqlalchemy import text
from sqlalchemy.orm import Session

from models import Airport, Airway, Fix, Nav
from services.database import SessionLocal

NMB2B_DIR = os.path.join(_SCRIPT_DIR, "..")
logger = LoggingService.get_logger("import_nm_b2b_data")

# NM B2B / AIXM namespaces (full URIs for ElementTree).
NS = {
    "adrmsg": "http://www.eurocontrol.int/cfmu/b2b/ADRMessage",
    "aixm": "http://www.aixm.aero/schema/5.1.1",
    "gml": "http://www.opengis.net/gml/3.2",
    "adrext": "http://www.aixm.aero/schema/5.1.1/extensions/EUR/ADR",
    "xlink": "http://www.w3.org/1999/xlink",
}
_XLINK_NS = NS["xlink"]
XLINK_HREF = f"{{{_XLINK_NS}}}href"

# Wrapper root with all ns declarations for parsing a single hasMember line.
_XML_WRAPPER = (
    "<root xmlns:adrmsg=\"" + NS["adrmsg"] + "\" xmlns:aixm=\"" + NS["aixm"]
    + "\" xmlns:gml=\"" + NS["gml"] + "\" xmlns:adrext=\"" + NS["adrext"]
    + "\" xmlns:xlink=\"" + NS["xlink"] + "\">%s</root>"
)


def _parse_pos(pos_text: str | None) -> tuple[float, float]:
    """
    Parse gml:pos content (lat lon) into (lat, lon) floats.

    Args:
        pos_text: Whitespace-separated "lat lon" string.

    Returns:
        (lat, lon) tuple.

    Raises:
        ValueError: If pos_text is missing or does not contain two numbers.
    """
    if not pos_text or not pos_text.strip():
        raise ValueError("pos text is empty")
    parts = pos_text.strip().split()
    if len(parts) == 2:
        raise ValueError("pos must have two numbers")
    return float(parts[0]), float(parts[1])


def uuid_from_href(href: str | None) -> str:
    """
    Extract UUID from xlink:href value like 'urn:uuid:...'.

    Args:
        href: The xlink:href attribute value.

    Returns:
        The UUID string (e.g. '49572bb2-87c2-4e5b-b837-57ad83a71822').

    Raises:
        ValueError: If href is missing or not urn:uuid:...
    """
    if not href or not href.strip().startswith("urn:uuid:"):
        raise ValueError("href must be urn:uuid:...")
    return href.strip().replace("urn:uuid:", "", 1)


def build_airway_id(
    prefix: str | None,
    second_letter: str | None,
    number: str | None,
) -> str:
    """
    Build airway_id from Route designator parts.

    Args:
        prefix: Optional designatorPrefix (e.g. 'K').
        second_letter: designatorSecondLetter (e.g. 'A', 'Z').
        number: designatorNumber (e.g. '100').

    Returns:
        Concatenated airway_id (e.g. 'A100', 'KZ159').
    """
    parts: list[str] = []
    if prefix:
        parts.append(prefix.strip())
    if second_letter is not None:
        parts.append(str(second_letter).strip())
    if number is not None:
        parts.append(str(number).strip())
    return "".join(parts)


def _text(elem: Any | None) -> str | None:
    """Return trimmed text content of an element or None."""
    if elem is None:
        return None
    t = elem.text
    return t.strip() if t else None


def _iter_baseline_lines(path: str) -> Generator[str, None, None]:
    """
    Yield each data line (hasMember) from a BASELINE file.

    Line 1 is the XML declaration and root, data lines start at line 2.

    Args:
        path: Path to the BASELINE file.

    Yields:
        Each non-empty line after the first.
    """
    with open(path, "r", encoding="utf-8") as fh:
        first = True
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if first:
                first = False
                continue
            yield line


def _parse_member_line(line: str) -> Any:
    """
    Wrap a single hasMember line in a root and parse to ElementTree.

    Args:
        line: One line of XML (one adrmsg:hasMember element).

    Returns:
        The parsed root element (child is the hasMember content).
    """
    wrapped = _XML_WRAPPER % line
    return ET.fromstring(wrapped)


def parse_airport_baseline(path: str) -> list[dict[str, Any]]:
    """
    Parse AirportHeliport.BASELINE into a list of airport records.

    Args:
        path: Path to AirportHeliport.BASELINE file.

    Returns:
        List of dicts with keys: code, name, lat, lon, uuid.
    """
    records: list[dict[str, Any]] = []
    for line in _iter_baseline_lines(path):
        try:
            root = _parse_member_line(line)
        except ET.ParseError as e:
            logger.warning("Parse error in airport line: %s", e)
            continue
        member = root.find(".//adrmsg:hasMember", NS)
        if member is None:
            member = root[0]
        airport = member.find("aixm:AirportHeliport", NS)
        if airport is None:
            continue
        ident_elem = airport.find("gml:identifier", NS)
        uuid_val = _text(ident_elem) if ident_elem is not None else None
        if not uuid_val:
            continue
        ts = airport.find(
            "aixm:timeSlice/aixm:AirportHeliportTimeSlice", NS
        )
        if ts is None:
            continue
        code_elem = ts.find("aixm:locationIndicatorICAO", NS)
        name_elem = ts.find("aixm:name", NS)
        arp = ts.find("aixm:ARP/aixm:ElevatedPoint", NS)
        pos_elem = arp.find("gml:pos", NS) if arp is not None else None
        code = _text(code_elem)
        name = _text(name_elem)
        if not code or pos_elem is None or pos_elem.text is None:
            continue
        try:
            lat, lon = _parse_pos(pos_elem.text)
        except ValueError:
            continue
        records.append({
            "code": code,
            "name": name or "",
            "lat": lat,
            "lon": lon,
            "uuid": uuid_val,
        })
    return records


def parse_designated_point_baseline(path: str) -> list[dict[str, Any]]:
    """
    Parse DesignatedPoint.BASELINE into a list of fix records.

    Args:
        path: Path to DesignatedPoint.BASELINE file.

    Returns:
        List of dicts with keys: identificator, lat, lon, uuid.
    """
    records: list[dict[str, Any]] = []
    for line in _iter_baseline_lines(path):
        try:
            root = _parse_member_line(line)
        except ET.ParseError as e:
            logger.warning("Parse error in DesignatedPoint line: %s", e)
            continue
        member = root.find(".//adrmsg:hasMember", NS)
        if member is None:
            member = root[0]
        dp = member.find("aixm:DesignatedPoint", NS)
        if dp is None:
            continue
        ident_elem = dp.find("gml:identifier", NS)
        uuid_val = _text(ident_elem) if ident_elem is not None else None
        if not uuid_val:
            continue
        ts = dp.find(
            "aixm:timeSlice/aixm:DesignatedPointTimeSlice", NS
        )
        if ts is None:
            continue
        name_elem = ts.find("aixm:name", NS)
        designator_elem = ts.find("aixm:designator", NS)
        identificator = _text(name_elem) or _text(designator_elem)
        loc = ts.find("aixm:location/aixm:Point", NS)
        pos_elem = loc.find("gml:pos", NS) if loc is not None else None
        if not identificator or pos_elem is None or pos_elem.text is None:
            continue
        try:
            lat, lon = _parse_pos(pos_elem.text)
        except ValueError:
            continue
        records.append({
            "identificator": identificator,
            "lat": lat,
            "lon": lon,
            "uuid": uuid_val,
        })
    return records


def parse_navaid_baseline(path: str) -> list[dict[str, Any]]:
    """
    Parse Navaid.BASELINE into list of nav records.

    Args:
        path: Path to Navaid.BASELINE file.

    Returns:
        List of dicts with keys: identificator, lat, lon, uuid.
    """
    records: list[dict[str, Any]] = []
    for line in _iter_baseline_lines(path):
        try:
            root = _parse_member_line(line)
        except ET.ParseError as e:
            logger.warning("Parse error in Navaid line: %s", e)
            continue
        member = root.find(".//adrmsg:hasMember", NS)
        if member is None:
            member = root[0]
        navaid = member.find("aixm:Navaid", NS)
        if navaid is None:
            continue
        ident_elem = navaid.find("gml:identifier", NS)
        uuid_val = _text(ident_elem) if ident_elem is not None else None
        if not uuid_val:
            continue
        ts = navaid.find("aixm:timeSlice/aixm:NavaidTimeSlice", NS)
        if ts is None:
            continue
        designator_elem = ts.find("aixm:designator", NS)
        loc = ts.find("aixm:location/aixm:ElevatedPoint", NS)
        pos_elem = loc.find("gml:pos", NS) if loc is not None else None
        identificator = _text(designator_elem)
        if not identificator or pos_elem is None or pos_elem.text is None:
            continue
        try:
            lat, lon = _parse_pos(pos_elem.text)
        except ValueError:
            continue
        records.append({
            "identificator": identificator,
            "lat": lat,
            "lon": lon,
            "uuid": uuid_val,
        })
    return records


def parse_route_baseline(path: str) -> dict[str, str]:
    """
    Parse Route.BASELINE into uuid -> airway_id map.

    Args:
        path: Path to Route.BASELINE file.

    Returns:
        Dict mapping Route uuid to airway_id string.
    """
    route_map: dict[str, str] = {}
    for line in _iter_baseline_lines(path):
        try:
            root = _parse_member_line(line)
        except ET.ParseError as e:
            logger.warning("Parse error in Route line: %s", e)
            continue
        member = root.find(".//adrmsg:hasMember", NS)
        if member is None:
            member = root[0]
        route = member.find("aixm:Route", NS)
        if route is None:
            continue
        ident_elem = route.find("gml:identifier", NS)
        uuid_val = _text(ident_elem) if ident_elem is not None else None
        if not uuid_val:
            continue
        ts = route.find("aixm:timeSlice/aixm:RouteTimeSlice", NS)
        if ts is None:
            continue
        prefix_elem = ts.find("aixm:designatorPrefix", NS)
        letter_elem = ts.find("aixm:designatorSecondLetter", NS)
        number_elem = ts.find("aixm:designatorNumber", NS)
        name_elem = ts.find("aixm:name", NS)
        prefix = _text(prefix_elem)
        letter = _text(letter_elem)
        number = _text(number_elem)
        airway_id = build_airway_id(prefix, letter, number)
        if not airway_id and name_elem is not None:
            airway_id = _text(name_elem)
        if airway_id:
            route_map[uuid_val] = airway_id
    return route_map


def _get_point_uuid_from_segment_point(
    ts: Any,
    start_or_end: str,
) -> str | None:
    """
    Get uuid from start or end EnRouteSegmentPoint.

    Handles pointChoice_fixDesignatedPoint and pointChoice_navaidSystem.

    Args:
        ts: RouteSegmentTimeSlice element.
        start_or_end: 'start' or 'end'.

    Returns:
        UUID string or None if not found.
    """
    point_elem = ts.find(f"aixm:{start_or_end}/aixm:EnRouteSegmentPoint", NS)
    if point_elem is None:
        return None
    fix_dp = point_elem.find("aixm:pointChoice_fixDesignatedPoint", NS)
    if fix_dp is not None:
        href = fix_dp.get(XLINK_HREF)
        if href:
            try:
                return uuid_from_href(href)
            except ValueError:
                pass
        return None
    navaid = point_elem.find("aixm:pointChoice_navaidSystem", NS)
    if navaid is not None:
        href = navaid.get(XLINK_HREF)
        if href:
            try:
                return uuid_from_href(href)
            except ValueError:
                pass
    return None


def parse_route_segment_baseline(
    path: str,
) -> Generator[dict[str, Any], None, None]:
    """
    Parse RouteSegment.BASELINE into segment records (generator).

    Args:
        path: Path to RouteSegment.BASELINE file.

    Yields:
        Dicts with keys: route_uuid, start_uuid, end_uuid.
    """
    for line in _iter_baseline_lines(path):
        try:
            root = _parse_member_line(line)
        except ET.ParseError as e:
            logger.warning("Parse error in RouteSegment line: %s", e)
            continue
        member = root.find(".//adrmsg:hasMember", NS)
        if member is None:
            member = root[0]
        seg = member.find("aixm:RouteSegment", NS)
        if seg is None:
            continue
        ts = seg.find(
            "aixm:timeSlice/aixm:RouteSegmentTimeSlice", NS
        )
        if ts is None:
            continue
        route_formed = ts.find("aixm:routeFormed", NS)
        route_href = route_formed.get(XLINK_HREF) if route_formed is not None else None
        if not route_href:
            continue
        try:
            route_uuid = uuid_from_href(route_href)
        except ValueError:
            continue
        start_uuid = _get_point_uuid_from_segment_point(ts, "start")
        end_uuid = _get_point_uuid_from_segment_point(ts, "end")
        if not start_uuid or not end_uuid:
            continue
        yield {
            "route_uuid": route_uuid,
            "start_uuid": start_uuid,
            "end_uuid": end_uuid,
        }


def import_airports(
    db: Session,
    records: list[dict[str, Any]],
    replace: bool = False,
) -> None:
    """
    Insert airport records into airport table.

    Args:
        db: SQLAlchemy session.
        records: List of dicts from parse_airport_baseline.
        replace: If False, skip records whose code already exists.
    """
    if not replace:
        existing = {row[0] for row in db.query(Airport.code).all()}
        records = [r for r in records if r["code"] not in existing]
    for rec in records:
        lat, lon = rec["lat"], rec["lon"]
        geom = WKTElement(f"POINT({lon} {lat})", srid=4326)
        airport = Airport(
            code=rec["code"],
            name=rec["name"] or None,
            lat=lat,
            lon=lon,
            geom=geom,
            uuid=rec["uuid"],
        )
        db.add(airport)
    db.commit()
    logger.info("Imported %d airports", len(records))


def import_fixes(db: Session, records: list[dict[str, Any]]) -> None:
    """
    Insert fix records into fix table.

    Args:
        db: SQLAlchemy session.
        records: List of dicts from parse_designated_point_baseline.
    """
    for rec in records:
        lat, lon = rec["lat"], rec["lon"]
        geom = WKTElement(f"POINT({lon} {lat})", srid=4326)
        fix = Fix(
            identificator=rec["identificator"],
            lat=lat,
            lon=lon,
            geom=geom,
            uuid=rec["uuid"],
        )
        db.add(fix)
    db.commit()
    logger.info("Imported %d fixes", len(records))


def import_navs(db: Session, records: list[dict[str, Any]]) -> None:
    """
    Insert nav records into nav table.

    Args:
        db: SQLAlchemy session.
        records: List of dicts from parse_navaid_baseline.
    """
    for rec in records:
        lat, lon = rec["lat"], rec["lon"]
        geom = WKTElement(f"POINT({lon} {lat})", srid=4326)
        nav = Nav(
            identificator=rec["identificator"],
            lat=lat,
            lon=lon,
            geom=geom,
            uuid=rec["uuid"],
        )
        db.add(nav)
    db.commit()
    logger.info("Imported %d navs", len(records))


def build_uuid_to_waypoint(
    fix_records: list[dict[str, Any]],
    nav_records: list[dict[str, Any]],
) -> dict[str, tuple[str, float, float]]:
    """
    Build uuid -> (identificator, lat, lon) from fix and nav records.

    Args:
        fix_records: From parse_designated_point_baseline.
        nav_records: From parse_navaid_baseline.

    Returns:
        Dict mapping uuid to (identificator, lat, lon).
    """
    result: dict[str, tuple[str, float, float]] = {}
    for rec in fix_records:
        result[rec["uuid"]] = (
            rec["identificator"],
            rec["lat"],
            rec["lon"],
        )
    for rec in nav_records:
        result[rec["uuid"]] = (
            rec["identificator"],
            rec["lat"],
            rec["lon"],
        )
    return result


def import_airways(
    db: Session,
    segments: Generator[dict[str, Any], None, None],
    route_map: dict[str, str],
    uuid_to_waypoint: dict[str, tuple[str, float, float]],
) -> None:
    """
    Insert airway segments into airway table.

    Args:
        db: SQLAlchemy session.
        segments: Generator from parse_route_segment_baseline.
        route_map: uuid -> airway_id from parse_route_baseline.
        uuid_to_waypoint: uuid -> (identificator, lat, lon) for fix+nav.
    """
    count = 0
    skipped = 0
    for seg in segments:
        route_uuid = seg["route_uuid"]
        airway_id = route_map.get(route_uuid)
        if not airway_id:
            logger.warning(
                "Route uuid %s not in route map, skip segment",
                route_uuid,
            )
            skipped += 1
            continue
        start_uuid = seg["start_uuid"]
        end_uuid = seg["end_uuid"]
        start_info = uuid_to_waypoint.get(start_uuid)
        end_info = uuid_to_waypoint.get(end_uuid)
        if not start_info or not end_info:
            logger.warning(
                "Missing waypoint for start=%s or end=%s, skip segment",
                start_uuid,
                end_uuid,
            )
            skipped += 1
            continue
        start_wp, start_lat, start_lon = start_info
        end_wp, end_lat, end_lon = end_info
        start_geom = WKTElement(
            f"POINT({start_lon} {start_lat})", srid=4326
        )
        end_geom = WKTElement(
            f"POINT({end_lon} {end_lat})", srid=4326
        )
        route_geom = WKTElement(
            f"LINESTRING({start_lon} {start_lat}, {end_lon} {end_lat})",
            srid=4326,
        )
        airway = Airway(
            start_waypoint=start_wp,
            start_lat=start_lat,
            start_lon=start_lon,
            end_waypoint=end_wp,
            end_lat=end_lat,
            end_lon=end_lon,
            airway_id=airway_id,
            start_geom=start_geom,
            end_geom=end_geom,
            route_geom=route_geom,
        )
        db.add(airway)
        count += 1
        if count % 5000 == 0:
            db.commit()
            logger.info("Airway progress: %d imported", count)
    db.commit()
    logger.info("Imported %d airways, skipped %d", count, skipped)


def truncate_tables(db: Session) -> None:
    """
    Truncate airport, fix, nav and airway tables.

    Args:
        db: SQLAlchemy session.
    """
    db.execute(
        text(
            "TRUNCATE TABLE airport, fix, nav, airway RESTART IDENTITY CASCADE"
        )
    )
    db.commit()
    logger.info("Truncated airport, fix, nav, airway")


def main() -> None:
    """Run NM B2B import: parse BASELINE files and insert into DB."""
    parser = argparse.ArgumentParser(
        description="Import NM B2B BASELINE data into database."
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Truncate airport, fix, nav, airway before import",
    )
    args = parser.parse_args()

    base = NMB2B_DIR
    airport_path = os.path.join(base, "AirportHeliport.BASELINE")
    dp_path = os.path.join(base, "DesignatedPoint.BASELINE")
    navaid_path = os.path.join(base, "Navaid.BASELINE")
    route_path = os.path.join(base, "Route.BASELINE")
    segment_path = os.path.join(base, "RouteSegment.BASELINE")

    for path in [
        airport_path,
        dp_path,
        navaid_path,
        route_path,
        segment_path,
    ]:
        if not os.path.isfile(path):
            logger.error("Missing file: %s", path)
            sys.exit(1)

    db = SessionLocal()
    try:
        if args.replace:
            truncate_tables(db)

        route_map = parse_route_baseline(route_path)
        logger.info("Loaded %d routes (airway_id map)", len(route_map))

        airport_records = parse_airport_baseline(airport_path)
        fix_records = parse_designated_point_baseline(dp_path)
        nav_records = parse_navaid_baseline(navaid_path)

        uuid_to_waypoint = build_uuid_to_waypoint(fix_records, nav_records)
        logger.info(
            "Waypoint map size: %d (fix + nav by uuid)",
            len(uuid_to_waypoint),
        )

        if airport_records:
            import_airports(db, airport_records, replace=args.replace)
        if fix_records:
            import_fixes(db, fix_records)
        if nav_records:
            import_navs(db, nav_records)

        segments = parse_route_segment_baseline(segment_path)
        import_airways(db, segments, route_map, uuid_to_waypoint)

    finally:
        db.close()


if __name__ == "__main__":
    main()
