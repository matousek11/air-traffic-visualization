from common.helpers.boundary_checker import BoundaryChecker
from common.helpers.logging_service import LoggingService
from common.helpers.physics_calculator import PhysicsCalculator
from common.helpers.mtcd_toolkit import FlightLike, MtcdToolkit, Conflict
from common.models.flight_position_adapter import FlightPositionAdapter
from common.helpers.flight_plan_engine import FlightPlanEngine

logger = LoggingService.get_logger(__name__)

class MtcdPipeline:
    LOOK_AHEAD_TIME_HORIZON = 0.5
    ACTIVE_DETECTION_TIME_HORIZON = 0.25

    def __init__(self):
        self.flight_plan_engine = FlightPlanEngine()
        self.boundary_checker = BoundaryChecker(self.flight_plan_engine)
        self.mtcd_toolkit = MtcdToolkit()

    def run_mtcd(
            self, flight_1: FlightPositionAdapter, flight_2: FlightPositionAdapter,
    ) -> list[Conflict]:
        """
        Detect conflicts between pairs of flights through the MTCD pipeline

        :return list of predicted conflicts
        """
        if flight_1.speed == 0 or flight_2.speed == 0:
            logger.info(
                "Flights %s and %s must have non-zero speed, skipping MTCD check",
                flight_1.flight_id, flight_2.flight_id,
            )

            return []

        # Parse the route string into a flight plan object
        if flight_1.route is None or flight_2.route is None:
            # TODO: run precise MTCD algorithm and return calculated data
            logger.info(
                "Flights %s and %s doesn't have route, running MTCD without route.",
                flight_1.flight_id,
                flight_2.flight_id,
            )
            closest_approach_point = self.mtcd_toolkit.calculate_closest_approach_point(
                self._flight_adapter_to_flight_like(flight_1),
                self._flight_adapter_to_flight_like(flight_2),
            )

            if closest_approach_point is None or closest_approach_point.time_to_conflict_entry > self.ACTIVE_DETECTION_TIME_HORIZON:
                return []

            if not self._is_conflict(
                    closest_approach_point.horizontal_distance,
                    closest_approach_point.vertical_distance,
                    closest_approach_point.time_to_closest_approach
            ):
                return []

            return [closest_approach_point]

        # TODO: possible optimization with caching of parsed flight plans as many checks with same flight can happen
        parsed_flightplan_1 = self.flight_plan_engine.process_flight_plan(flight_1.flight_id, flight_1.route)
        parsed_flightplan_2 = self.flight_plan_engine.process_flight_plan(flight_2.flight_id, flight_2.route)
        if len(parsed_flightplan_1.segments) <= 1 or len(parsed_flightplan_2.segments) <= 1:
            return []

        logger.info("Cutting routes to MTCD time horizon.")
        # cut flight plan to 30 min ahead
        upcoming_waypoint_index_1 = self.flight_plan_engine.upcoming_waypoint_in_plan(
            flight_1.lat,
            flight_1.lon,
            parsed_flightplan_1,
        )
        
        parsed_flightplan_1 = self.flight_plan_engine.calculate_route_for_upcoming_horizon(
            self.LOOK_AHEAD_TIME_HORIZON,
            flight_1,
            upcoming_waypoint_index_1,
            parsed_flightplan_1,
        )

        upcoming_waypoint_index_2 = self.flight_plan_engine.upcoming_waypoint_in_plan(
            flight_2.lat,
            flight_2.lon,
            parsed_flightplan_2,
        )
        parsed_flightplan_2 = self.flight_plan_engine.calculate_route_for_upcoming_horizon(
            self.LOOK_AHEAD_TIME_HORIZON,
            flight_2,
            upcoming_waypoint_index_2,
            parsed_flightplan_2,
        )

        # whole route vertical boundary check
        logger.info("Checking boundary intersection of routes.")
        if not self.boundary_checker.has_intersection(
                parsed_flightplan_1.segments,
                parsed_flightplan_2.segments,
        ):
            # Conflict not possible
            logger.info("Routes doesn't have intersections.")
            return []

        # segment horizontal and vertical boundary check
        logger.info("Searching for conflicting segments of routes.")
        conflicting_segments = self.boundary_checker.get_conflicting_segments(
            parsed_flightplan_1, parsed_flightplan_2,
        )

        if len(conflicting_segments) == 0:
            # conflicts doesn't exists
            logger.info("No conflicting segments of routes.")
            return []

        # extrapolate and check time boundary of flights for segment
        logger.info("Checking time windows of segments.")
        conflicting_segments = self.boundary_checker.get_conflict_segments_within_time_boundaries(
            flight_1,
            flight_2,
            parsed_flightplan_1.segments,
            parsed_flightplan_2.segments,
            conflicting_segments,
        )

        if len(conflicting_segments) == 0:
            # conflicts doesn't exists
            logger.info("No time windows between segments.")
            return []

        # TODO: there can be more than one conflict between same flights, how to represent it?
        #   How to know which mtcd to update then?
        # Get position of flights when later plane enter segment
            # later entry time is the time when we are interested in location of the second flight
            # first flight will be at position of waypoint
            # precise MTCD will have time boundary of the remaining time to the first exit of segment of any flight
        pairs_for_precise_mtcd: list[tuple[FlightLike, FlightLike, float]] = []
        for conflicting_segment in conflicting_segments:
            pairs_for_precise_mtcd.append(self.flight_plan_engine.get_flight_prediction_for_segments(
                parsed_flightplan_1.segments,
                parsed_flightplan_2.segments,
                conflicting_segment,
            ))
        logger.info(
            "%d pairs of segments for precise MTCD check found.",
            len(pairs_for_precise_mtcd),
        )

        detected_conflicts: list[Conflict] = []
        for pair_for_precise_mtcd in pairs_for_precise_mtcd:
            pair_flight_1, pair_flight_2, time_horizon = pair_for_precise_mtcd
            closest_approach_point = self.mtcd_toolkit.calculate_closest_approach_point(
                pair_flight_1, pair_flight_2,
            )
            logger.info(closest_approach_point)
            time_horizon = min(time_horizon, self.ACTIVE_DETECTION_TIME_HORIZON)
            logger.info("Time horizon for precise MTCD: %f", time_horizon)

            if closest_approach_point is None or closest_approach_point.time_to_conflict_entry > time_horizon:
                # Conflict isn't detected or is beyond the segment we are interested in
                logger.info(
                    "One conflict pair skipped because it doesn't have CPA or is beyond the segment time horizon."
                )
                logger.info(
                    "Time to conflict entry: %f, segment time horizon: %f",
                    closest_approach_point.time_to_conflict_entry if closest_approach_point is not None else -1,
                    time_horizon,
                )
                continue

            logger.info(
                "Time to closest approach point: %f",
                closest_approach_point.time_to_closest_approach,
            )
            if self._is_conflict(
                closest_approach_point.horizontal_distance,
                closest_approach_point.vertical_distance,
                closest_approach_point.time_to_closest_approach
            ):
                detected_conflicts.append(closest_approach_point)

            if len(detected_conflicts) == 0:
                logger.info("No conflicts detected with precise MTCD.")
            else:
                logger.info(
                    "%d conflicts detected with precise MTCD.",
                    len(detected_conflicts),
                )

        return detected_conflicts

    def _is_conflict(
            self,
            horizontal_distance: float,
            vertical_distance: float,
            time_to_closest_approach: float,
    ) -> bool:
        """Validates whether minimum distance is going to be violated"""
        # Typical separation minima: 5 NM horizontal, 1000 ft vertical
        return (
                horizontal_distance < 5.0  # 5 nautical miles
                and abs(vertical_distance)
                < PhysicsCalculator.feet_to_nautical_miles(1000)
                and time_to_closest_approach >= 0
        )

    def _flight_adapter_to_flight_like(
            self,
            flight_adapter: FlightPositionAdapter
    ) -> FlightLike:
        """Convert flight data to DTO from MTCD algorithm"""
        return FlightLike(
            flight_adapter.lat,
            flight_adapter.lon,
            flight_adapter.flight_level,
            flight_adapter.speed,
            flight_adapter.track_heading,
            flight_adapter.vertical_speed,
        )
