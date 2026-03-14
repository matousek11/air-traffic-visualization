from typing import List

from models import Airway, FlightPosition, Fix, Nav
from common.models.flight_parser.enriched_flight_plan import EnrichedFlightPlan
from common.models.flight_parser.enriched_route_segment import EnrichedRouteSegment
from common.models.flight_parser.parsed_flight_plan import ParsedFlightPlan
from common.models.flight_parser.raw_route_segment import RawRouteSegment
from common.models.flight_parser.waypoint import Waypoint
from repositories.airway_repository import AirwayRepository
from repositories.fix_repository import FixRepository
from repositories.nav_repository import NavRepository


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
            enriched_segments += airway_enriched_segments

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

    def get_point(self, lat: float, lon: float, identifier: str) -> Fix | Nav:
        """Finds closest navigation point to given coordinates."""
        point: Fix | Nav | None = FixRepository.get_closest_fix(
            lat,
            lon,
            identifier
        )

        if point is None:
            point = NavRepository.get_closest_nav_or_fail(
                lat,
                lon,
                identifier
            )

        return point

    def get_airway_waypoints(
            self,
            airway_id: str,
            start_waypoint: str,
            end_waypoint: str,
            true_air_speed: int,
            flight_level: int
    ) -> list[EnrichedRouteSegment]:
        """
        Get list of waypoints forming a path through an airway from start to end waypoint.

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
            raise ValueError(f"No segments found for {start_waypoint} in airway {airway_id}")

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

            raise ValueError(f"Route {airway_id} doesn't exists")

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
                raise ValueError(f"Route {airway_id} doesn't exists")

            return self._convert_identifiers_into_enriched_segments(
                waypoints,
                start_segments[0].start_lat,
                start_segments[0].start_lon,
                true_air_speed,
                flight_level
            )

        raise ValueError(f"More than two segments found for {start_waypoint} in airway {airway_id}")

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

    def _get_points_to_end_waypoint(
            self,
            start_segment: Airway,
            segments: list[Airway],
            start_waypoint: str,
            end_waypoint: str
    ) -> List[str] | None:
        """
        Traverse airway segments from start_waypoint until end_waypoint is reached.

        :param start_segment: segment of airway from which to start traversal
        :param segments: all segments of airway
        :param start_waypoint: identifier of start waypoint
        :param end_waypoint: identifier of end waypoint
        :return: list of identifiers of waypoints traversed from start_waypoint to end_waypoint
        """
        waypoints: list[str] = [start_waypoint]
        searched_waypoint = start_segment.get_next_point(start_waypoint)

        while searched_waypoint != end_waypoint:
            # segments that contain searched waypoint but doesn't connect to already traversed waypoint
            found_segments = [
                seg for seg in segments
                if seg.start_waypoint == searched_waypoint and seg.end_waypoint != waypoints[-1]
                   or seg.end_waypoint == searched_waypoint and seg.start_waypoint != waypoints[-1]
            ]

            if len(found_segments) == 0:
                raise ValueError(f"Waypoint {searched_waypoint} not found in airway {start_segment.airway_id}")

            if len(found_segments) > 1:
                raise ValueError(f"More results than expected for airway with point {searched_waypoint}")

            waypoints.append(searched_waypoint)
            searched_waypoint = found_segments[0].get_next_point(searched_waypoint)

        waypoints.append(searched_waypoint)
        return waypoints






