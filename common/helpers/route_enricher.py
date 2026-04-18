"""Route string enrichment using fix/nav/airway data from the database."""
import math
from collections import deque
from typing import List
import re

from common.helpers.logging_service import LoggingService
from common.helpers.physics_calculator import PhysicsCalculator
from common.models.flight_parser.enriched_flight_plan import EnrichedFlightPlan
from common.models.flight_parser.enriched_route_segment import EnrichedRouteSegment
from common.models.flight_parser.parsed_flight_plan import ParsedFlightPlan
from common.models.flight_parser.raw_route_segment import RawRouteSegment
from common.models.flight_parser.waypoint import Waypoint
from models import Airway, FlightPosition, Fix, Nav
from repositories.airway_repository import AirwayRepository
from repositories.coord_lookup_cache import CachedCoordinates
from repositories.fix_repository import FixRepository
from repositories.nav_repository import NavRepository

logger = LoggingService.get_logger(__name__)


class RouteEnricher:
    """House flight plan enrichment logic."""
    def __init__(self):
        self.current_true_air_speed: int | None = None
        self.current_flight_level: int | None = None

    def enrich(
            self,
            flight_position: FlightPosition,
            parsed_flight_plan: ParsedFlightPlan
    ) -> EnrichedFlightPlan:
        """Enrich parsed flight plan with position data and airway waypoints"""
        self.current_true_air_speed: int | None = None
        self.current_flight_level: int | None = None
        logger.info(logger.info(f"Enriching flight plan: {parsed_flight_plan}"))

        if parsed_flight_plan.config is not None:
            self.current_true_air_speed = parsed_flight_plan.config.true_air_speed
            self.current_flight_level = parsed_flight_plan.config.flight_level
        else:
            # TODO: must be revisited and recalculated for KTAS from ground speed
            self.current_true_air_speed = flight_position.ground_speed_kt
            self.current_flight_level = flight_position.flight_level

        enriched_segments: list[EnrichedRouteSegment] = []

        for index, segment in enumerate(parsed_flight_plan.segments):
            if segment.true_air_speed is not None:
                self.current_true_air_speed = segment.true_air_speed

            if segment.flight_level is not None:
                self.current_flight_level = segment.flight_level

            if segment.via_airway is None or segment.via_airway == "DCT":
                # doesn't contain airway append just waypoint
                enriched_segments.append(
                    self._enrich_single_segment(flight_position, segment)
                )
                continue

            if index + 1 >= len(parsed_flight_plan.segments):
                raise ValueError(f"Next segment after {segment.ident} doesn't exist but it should")

            airway_enriched_segments = self.get_airway_waypoints(
                segment.via_airway,
                segment.ident,
                parsed_flight_plan.segments[index + 1].ident,
                int(self.current_true_air_speed),
                int(self.current_flight_level)
            )
            if len(airway_enriched_segments) != 0:
                enriched_segments += airway_enriched_segments

        # Get rid of duplicate segments
        deduped: list[EnrichedRouteSegment] = []
        for segment in enriched_segments:
            if deduped and deduped[-1].ident == segment.ident:
                continue
            deduped.append(segment)
        enriched_segments = deduped

        return EnrichedFlightPlan(
            config=parsed_flight_plan.config,
            segments=enriched_segments,
            departure_procedure=parsed_flight_plan.departure_procedure,
            arrival_procedure=parsed_flight_plan.arrival_procedure,
        )

    def _enrich_single_segment(
            self,
            flight_position: FlightPosition,
            segment: RawRouteSegment
    ) -> EnrichedRouteSegment:
        """Enrich the single segment when on airway is set"""
        true_air_speed = segment.true_air_speed if segment.true_air_speed is not None \
            else self.current_true_air_speed
        flight_level = segment.flight_level if segment.flight_level is not None \
            else self.current_flight_level

        point = self.get_point(flight_position.lat, flight_position.lon, segment.ident)
        waypoint = Waypoint(lat=point.lat, lon=point.lon)

        return EnrichedRouteSegment(
            ident=segment.ident,
            waypoint=waypoint,
            true_air_speed=true_air_speed,
            flight_level=flight_level
        )

    def get_point(
        self,
        lat: float,
        lon: float,
        identifier: str,
    ) -> Fix | Nav | CachedCoordinates:
        """Finds navigation point to given coordinates.

        Args:
            lat: Latitude in degrees.
            lon: Longitude in degrees.
            identifier: Fix or nav identifier.

        Returns:
            ``Fix`` or ``Nav`` row, or ``CachedCoordinates`` when served from
            the repository cache or is ad hoc point.
        """
        coordinate = self._get_coordinate(identifier)
        if coordinate is not None:
            return coordinate

        coordinate = self._get_place_bearing_distance_position(lat, lon, identifier)
        if coordinate is not None:
            return coordinate

        point: Fix | Nav | CachedCoordinates | None = (
            FixRepository.get_closest_fix(
                lat,
                lon,
                identifier,
            )
        )
        if point is not None:
            return point

        return NavRepository.get_closest_nav_or_fail(
            lat,
            lon,
            identifier,
        )


    def get_airway_waypoints(
            self,
            airway_id: str,
            start_waypoint: str,
            end_waypoint: str,
            true_air_speed: int,
            flight_level: int
    ) -> list[EnrichedRouteSegment]:
        """
        Get a list of waypoints forming a path through an airway from start to end waypoint.

        Args:
            airway_id: ICAO airway identifier
            start_waypoint: Starting waypoint identifier
            end_waypoint: Ending waypoint identifier
            true_air_speed: True air speed in knots on current waypoint
            flight_level: flight level in feets on current waypoint

        Returns:
            List of Waypoint objects representing the path through the airway
        """

        airway_segments: list[Airway] = AirwayRepository.get_airway_segments(airway_id)
        # Finds segments that contain start_waypoint
        start_segments = [
            seg for seg in airway_segments
            if seg.start_waypoint == start_waypoint or seg.end_waypoint == start_waypoint
        ]

        if len(start_segments) == 0:
            # Ignore missing segments as there could be waypoints that are out of europe scope
            return []

        if len(start_segments) == 1:
            waypoints = self._get_points_to_end_waypoint(start_segments[0], airway_segments, start_waypoint, end_waypoint)
            if waypoints is not None:
                return self._convert_identifiers_into_enriched_segments(
                    waypoints,
                    start_segments[0].start_lat,
                    start_segments[0].start_lon,
                    true_air_speed,
                    flight_level
                )

            logger.error(f"Route {airway_id} doesn't exists, skipping further route enrichment")
            return []

        if len(start_segments) == 2:
            waypoints = self._get_points_to_end_waypoint(start_segments[0], airway_segments, start_waypoint, end_waypoint)
            if waypoints is not None:
                return self._convert_identifiers_into_enriched_segments(
                    waypoints,
                    start_segments[0].start_lat,
                    start_segments[0].start_lon,
                    true_air_speed,
                    flight_level
                )

            waypoints = self._get_points_to_end_waypoint(start_segments[1], airway_segments, start_waypoint, end_waypoint)
            if waypoints is None:
                logger.error(f"Route {airway_id} doesn't exists, skipping further route enrichment")
                return []

            return self._convert_identifiers_into_enriched_segments(
                waypoints,
                start_segments[0].start_lat,
                start_segments[0].start_lon,
                true_air_speed,
                flight_level
            )

        logger.error(f"More than two segments found for {start_waypoint} in airway {airway_id}")
        return []

    def _get_coordinate(self, identifier: str) -> CachedCoordinates | None:
        """Parse coordinate string and returns its position"""
        coord_match = re.match(
            r"^(\d{2})(\d{2})?([NS])(\d{3})(\d{2})?([EW])$",
            identifier
        )
        if not coord_match:
            return None

        lat_deg, lat_min, lat_hem, lon_deg, lon_min, lon_hem = coord_match.groups()

        dec_lat = float(lat_deg) + (float(lat_min or 0) / 60.0)
        if lat_hem == 'S':
            dec_lat *= -1

        dec_lon = float(lon_deg) + (float(lon_min or 0) / 60.0)
        if lon_hem == 'W':
            dec_lon *= -1

        return CachedCoordinates(
            lat=dec_lat,
            lon=dec_lon,
        )

    def _get_place_bearing_distance_position(
            self,
            lat: float,
            lon: float,
            identifier: str,
    ) -> CachedCoordinates | None:
        """
        Get pos from a polar coordinate system where anchor is wpy with identifieer

        :param lat: lat of previous wpy or lat of plane pos
        :param lon: lon of previous wpy or lon of plane pos
        :param identifier: identifier of point from which position is calculated
        :return: Coordinates when possible to calculate, otherwise None
        """
        pbd_match = re.match(r"^([A-Z]{2,3})(\d{3})(\d{3})$", identifier)
        if pbd_match is None:
            return None
        ref_id, bearing_deg, dist_nm = pbd_match.groups()

        # find referential point
        ref_nav = self.get_point(lat, lon, ref_id)

        # convert nm to km
        dist_km = PhysicsCalculator.nm_to_km(float(dist_nm))
        bearing_rad = math.radians(float(bearing_deg))

        # Calculate offsets (North a East)
        north_offset = dist_km * math.cos(bearing_rad)
        east_offset = dist_km * math.sin(bearing_rad)

        # get pos from relative pos
        new_pos = PhysicsCalculator.enu_to_latlon(
            east=east_offset,
            north=north_offset,
            up=0,
            ref_lat=ref_nav.lat,
            ref_lon=ref_nav.lon,
            ref_fl=0
        )

        return CachedCoordinates(
            lat=new_pos.lat,
            lon=new_pos.lon
        )

    def _convert_identifiers_into_enriched_segments(
            self,
            identifiers: list[str],
            lat: float,
            lon: float,
            true_air_speed: int,
            flight_level: int
    ) -> list[EnrichedRouteSegment]:
        """Map identifiers from airway into Enriched waypoints"""
        enriched_segments: list[EnrichedRouteSegment] = []
        for ident in identifiers:
            point = self.get_point(lat, lon, ident)
            enriched_segment = EnrichedRouteSegment(
                ident=ident,
                waypoint=Waypoint(lat=point.lat, lon=point.lon),
                true_air_speed=true_air_speed,
                flight_level=flight_level
            )

            enriched_segments.append(enriched_segment)

        return enriched_segments

    @staticmethod
    def _build_airway_adjacency(segments: list[Airway]) -> dict[str, list[str]]:
        """Build an undirected adjacency map from airway segment endpoints.

        Args:
            segments: All ``Airway`` rows for one airway identifier.

        Returns:
            Mapping from each waypoint id to sorted adjacent waypoint ids.
        """
        adj: dict[str, set[str]] = {}
        for seg in segments:
            a = seg.start_waypoint
            b = seg.end_waypoint
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
        return {w: sorted(neighbors) for w, neighbors in adj.items()}

    @staticmethod
    def _reconstruct_path(
            parent: dict[str, str],
            start_waypoint: str,
            end_waypoint: str,
    ) -> list[str]:
        """Rebuild the start-to-end path using BFS parent links.

        Args:
            parent: For each visited node (except ``start_waypoint``), the
                previous node on the BFS tree.
            start_waypoint: Path origin.
            end_waypoint: Path destination.

        Returns:
            Waypoint identifiers from ``start_waypoint`` to ``end_waypoint``.
        """
        reversed_path: list[str] = []
        current_waypoint: str | None = end_waypoint
        while current_waypoint is not None and current_waypoint != start_waypoint:
            reversed_path.append(current_waypoint)
            current_waypoint = parent.get(current_waypoint)
        reversed_path.append(start_waypoint)
        return list(reversed(reversed_path))


    def _find_path_with_first_edge(
            self,
            start_segment: Airway,
            segments: list[Airway],
            start_waypoint: str,
            end_waypoint: str,
    ) -> list[str] | None:
        """The shortest path to end waypoint.

        Args:
            start_segment: Segment that fixes the initial direction from
                ``start_waypoint``.
            segments: All segments of the airway (graph edges).
            start_waypoint: Route start fix id.
            end_waypoint: Route end fix id.

        Returns:
            List of waypoint ids along the path, or ``None`` if no such path
            exists.
        """
        first_next = start_segment.get_next_point(start_waypoint)
        if first_next == end_waypoint:
            return [start_waypoint, end_waypoint]

        adj = self._build_airway_adjacency(segments)
        if end_waypoint not in adj:
            return None

        parent: dict[str, str] = {first_next: start_waypoint}
        visited: set[str] = {start_waypoint, first_next}
        queue: deque[str] = deque([first_next])

        while queue:
            node = queue.popleft()
            if node == end_waypoint:
                return self._reconstruct_path(
                    parent,
                    start_waypoint,
                    end_waypoint,
                )
            for neighbor in adj.get(node, []):
                if neighbor in visited:
                    continue
                if neighbor == start_waypoint:
                    continue
                visited.add(neighbor)
                parent[neighbor] = node
                queue.append(neighbor)

        return None


    def _get_points_to_end_waypoint(
            self,
            start_segment: Airway,
            segments: list[Airway],
            start_waypoint: str,
            end_waypoint: str
    ) -> List[str] | None:
        """Find waypoint ids from start to end along one airway branch of the graph.


        Args:
            start_segment: Segment of airway from which to start traversal.
            segments: All segments of airway.
            start_waypoint: Identifier of start waypoint.
            end_waypoint: Identifier of end waypoint.

        Returns:
            List of identifiers from ``start_waypoint`` to ``end_waypoint``,
            or ``None`` if no path exists with the required first edge.
        """
        return self._find_path_with_first_edge(
            start_segment,
            segments,
            start_waypoint,
            end_waypoint,
        )






