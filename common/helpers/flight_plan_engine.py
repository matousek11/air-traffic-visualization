import copy

import numpy as np

from common.helpers.logging_service import LoggingService
from common.types.conflicting_segments_with_time import ConflictingSegmentWithTime
from common.helpers.mtcd_toolkit import FlightLike
from common.helpers.physics_calculator import PhysicsCalculator
from common.models.flight_position_adapter import FlightPositionAdapter
from common.models.flight_parser.enriched_flight_plan import EnrichedFlightPlan
from common.models.flight_parser.enriched_route_segment import EnrichedRouteSegment
from common.models.flight_parser.waypoint import Waypoint
from repositories.flight_position_repository import FlightPositionRepository
from common.helpers.route_enricher import RouteEnricher
from common.helpers.route_parser import RouteParser


logger = LoggingService.get_logger(__name__)

class FlightPlanEngine:
    """
    Handle parsing of string flight plan to EnrichedFlightPlan
    """
    def __init__(self):
        self.parser = RouteParser()
        self.enricher = RouteEnricher()
        self.physics_calculator = PhysicsCalculator()

    def process_flight_plan(self, flight_id: str, raw_string: str) -> EnrichedFlightPlan:
        """
        Handle parsing of string flight plan to EnrichedFlightPlan

        :param flight_id: ID of the flight like CSA201
        :param raw_string: String flight plan like "DENUT L610 LAM"
        """
        # 1. Parse string
        raw_parsed_flightplan = self.parser.parse(raw_string)

        # get flight details
        flight_position = FlightPositionRepository.get_latest_position(flight_id)

        # 2. Enrich flight plan with Data
        return self.enricher.enrich(flight_position, raw_parsed_flightplan)

    def upcoming_waypoint_in_plan(
            self,
            flight_lat: float,
            flight_lon: float,
            plan: EnrichedFlightPlan
    ) -> int:
        """Returns index of upcoming waypoint"""
        logger.info("Segments: %s", plan.segments)
        for i in range(len(plan.segments) - 1):
            a = plan.segments[i].waypoint
            b = plan.segments[i + 1].waypoint

            progress = self._get_progress(flight_lat, flight_lon, a, b)

            # if progress < 1.0, waypoint B is still ahead of plane
            if progress < 1.0:
                if progress >= 0:
                    # Plane is on segment A -> B, next waypoint is B (index i+1)
                    return i + 1
                # Plane is before A, keep from waypoint A (index i)
                return i

        # return the last waypoint when we get to the end of plan
        return len(plan.segments) - 1

    def calculate_route_for_upcoming_horizon(
            self,
            time_horizon: float,
            flight: FlightPositionAdapter,
            upcoming_waypoint_index: int,
            plan: EnrichedFlightPlan
    ) -> EnrichedFlightPlan:
        """
        Modify segments in the plan and leave only those that can be reached in the select time horizon.
        As the first point in route is prepended current position of the flight with its data.

        :param time_horizon: Time horizon in hours
        :param flight:
        :param upcoming_waypoint_index: Index of upcoming waypoint for flight
        :param plan: EnrichedFlightPlan

        :return: EnrichedFlightPlan modified plan with segments that will be reached in feature up to the selected time horizon
        """
        miles_threshold = flight.speed * time_horizon
        track_miles = 0
        logger.info("Full route: %s", " ".join(segment.ident for segment in plan.segments))
        new_plan = copy.copy(plan)
        new_plan.segments = plan.segments[upcoming_waypoint_index:]
        logger.info("Upcoming waypoint index: %d", upcoming_waypoint_index)
        reachable_segments = []
        last_lat, last_lon = flight.lat, flight.lon

        for segment in new_plan.segments:
            distance_in_km = self.physics_calculator.get_distance_between_positions(
                 last_lat, last_lon,
                 segment.waypoint.lat,
                 segment.waypoint.lon,
            )

            track_miles += PhysicsCalculator.km_to_nm(distance_in_km)
            reachable_segments.append(segment)
            last_lat, last_lon = segment.waypoint.lat, segment.waypoint.lon

            if track_miles > miles_threshold:
                break

        new_plan.segments = reachable_segments
        logger.info("Cut route: %s", " ".join(segment.ident for segment in new_plan.segments))
        return self._prepend_current_position(new_plan, flight)

    def calculate_track_miles_to_waypoint(
            self,
            flight: FlightPositionAdapter,
            targeted_waypoint_index: int,
            segments: list[EnrichedRouteSegment],
    ) -> float:
        """
        Calculate track miles to select waypoint from current position of flight

        :param flight: flight from which to calculate track miles to waypoint
        :param targeted_waypoint_index: index of target waypoint in segments
        :param segments: segments through which track miles to waypoint will be calculated,
        first segment must be upcoming waypoint for flight

        :return: remaining track miles to waypoint
        """
        track_kilometers = 0
        previous_segment_lat = flight.lat
        previous_segment_lon = flight.lon
        for index, segment in enumerate(segments):
            track_kilometers += self.physics_calculator.get_distance_between_positions(
                previous_segment_lat,
                previous_segment_lon,
                segment.waypoint.lat,
                segment.waypoint.lon,
            )

            previous_segment_lat = segment.waypoint.lat
            previous_segment_lon = segment.waypoint.lon

            if targeted_waypoint_index == index:
                return PhysicsCalculator.km_to_nm(track_kilometers)

        return PhysicsCalculator.km_to_nm(track_kilometers)

    def get_flight_prediction_for_segments(
            self,
            segments_1: list[EnrichedRouteSegment],
            segments_2: list[EnrichedRouteSegment],
            conf: ConflictingSegmentWithTime,
    ) -> tuple[FlightLike, FlightLike, float]:
        """
        Calculate positions of flights in a moment where latter plane enter segments where conflict can happen,
        also calculates time horizon in which flight conflict can happen as later on flights can change heading.

        :param segments_1: segments of first flight
        :param segments_2: segments of second flight
        :param conf: information about conflict in selected segments

        :return: Positions of flights when both are in segments and time horizon in which MTCD can be detected
        """

        # Calculate common time window
        segment_entry_time = max(conf.flight_1_segment_entry_time, conf.flight_2_segment_entry_time)
        segment_exit_time = min(conf.flight_1_segment_exit_time, conf.flight_2_segment_exit_time)
        mtcd_horizon = segment_exit_time - segment_entry_time

        def _create_flight_prediction(
                segments: list[EnrichedRouteSegment],
                start_idx: int,
                end_idx: int,
                entry_time: float,
                exit_time: float,
        ) -> FlightLike:
            """
            Interpolates position for flight in time of entry of flight that is entering later

            :param segments: segments of interpolated flight
            :param start_idx: segment index
            :param end_idx: segment index
            :param entry_time: for segment in minutes
            :param exit_time: for segment in minutes
            :return:
            """
            seg_start = segments[start_idx]
            seg_end = segments[end_idx]

            # Calculate t for interpolation
            duration = exit_time - entry_time
            if duration <= 0:
                raise ValueError("Duration of segment should be positive")
            elapsed = segment_entry_time - entry_time
            t = elapsed / duration

            # Interpolate position
            lat = seg_start.waypoint.lat + (seg_end.waypoint.lat - seg_start.waypoint.lat) * t
            lon = seg_start.waypoint.lon + (seg_end.waypoint.lon - seg_start.waypoint.lon) * t

            # Interpolate flight level
            current_fl = seg_start.flight_level + (seg_end.flight_level - seg_start.flight_level) * t

            # Calculate vertical speed
            altitude_diff_ft = (seg_end.flight_level - seg_start.flight_level) * 100
            v_speed = altitude_diff_ft / duration

            heading = self.physics_calculator.calculate_heading(
                seg_start.waypoint.lat, seg_start.waypoint.lon,
                seg_end.waypoint.lat, seg_end.waypoint.lon
            )
            logger.info("Checking segment from %s to %s", seg_start.ident, seg_end.ident)
            logger.info("Segment start: lat: %f, lon: %f", seg_start.waypoint.lat, seg_start.waypoint.lon)
            logger.info("Segment end: lat: %f, lon: %f", seg_end.waypoint.lat, seg_end.waypoint.lon)
            logger.info("Interpolated pos: lat: %f, lon: %f", lat, lon)

            return FlightLike(
                lat,
                lon,
                int(current_fl),
                seg_start.true_air_speed, # TODO: should be ground speed and maybe also gs of flight at current time when plane is already in segment
                int(heading),
                v_speed
            )

        # Get predictions for both flights
        flight_1 = _create_flight_prediction(
            segments_1, conf.flight_1_segment_start_index, conf.flight_1_segment_end_index,
            conf.flight_1_segment_entry_time, conf.flight_1_segment_exit_time
        )

        flight_2 = _create_flight_prediction(
            segments_2, conf.flight_2_segment_start_index, conf.flight_2_segment_end_index,
            conf.flight_2_segment_entry_time, conf.flight_2_segment_exit_time
        )

        return flight_1, flight_2, mtcd_horizon

    def _get_progress(
            self,
            plane_lat: float,
            plane_lon: float,
            a_point: Waypoint,
            b_point: Waypoint,
    ) -> float:
        """
        Calculate interpolation coefficient t between two waypoints in flight plan
        """
        cos_lat = np.cos(np.radians(
            (a_point.lat + b_point.lat) / 2
        ))
        a = np.array([a_point.lat, a_point.lon * cos_lat])
        b = np.array([b_point.lat, b_point.lon * cos_lat])
        p = np.array([plane_lat, plane_lon * cos_lat])
        u = b - a
        v = p - a
        denominator = np.dot(u, u)
        if denominator == 0:
            return 1.1
        return np.dot(v, u) / denominator

    def _prepend_current_position(
            self,
            plan: EnrichedFlightPlan,
            flight: FlightPositionAdapter,
    ) -> EnrichedFlightPlan:
        """
        Prepends current flight position as the first point of flight plan for collision detection.

        :param tas: true air speed in knots
        :param flight_level: altitude in 100 of feets
        :return: Update enriched flight plan
        """
        plane_segment = EnrichedRouteSegment(
            "current_flight_pos",
            Waypoint(flight.lat, flight.lon),
            flight.speed,
            flight.flight_level,
        )

        plan.segments.insert(0, plane_segment)
        return plan