"""MTCD pipeline: route checks, time sync, closest-approach detection."""

from datetime import datetime

from common.helpers.boundary_checker import BoundaryChecker
from common.helpers.logging_service import LoggingService
from common.helpers.physics_calculator import PhysicsCalculator
from common.helpers.mtcd_toolkit import FlightLike, MtcdToolkit, Conflict
from common.models.flight_position_adapter import FlightPositionAdapter
from common.helpers.flight_plan_engine import FlightPlanEngine

logger = LoggingService.get_logger(__name__)


class MtcdPipeline:
    """Runs MTCD checks for a pair of flights (route-based or kinematic)."""

    LOOK_AHEAD_TIME_HORIZON = 0.5
    ACTIVE_DETECTION_TIME_HORIZON = 0.25
    TIME_SKEW_SYNC_THRESHOLD_SECONDS = 10

    def __init__(self):
        self.flight_plan_engine = FlightPlanEngine()
        self.boundary_checker = BoundaryChecker(self.flight_plan_engine)
        self.mtcd_toolkit = MtcdToolkit()

    def run_mtcd(
            self,
            flight_1: FlightPositionAdapter,
            flight_2: FlightPositionAdapter,
    ) -> list[Conflict]:
        """
        Detect conflicts between pairs of flights through the MTCD pipeline

        :return list of predicted conflicts
        """
        if flight_1.speed == 0 or flight_2.speed == 0:
            logger.info(
                "Flights %s and %s must have non-zero speed, "
                "skipping MTCD check",
                flight_1.flight_id,
                flight_2.flight_id,
            )

            return []

        flight_1, flight_2 = self._align_positions_to_common_time(
            flight_1,
            flight_2,
        )

        # Parse the route string into a flight plan object
        if flight_1.route is None or flight_2.route is None:
            # TODO: run precise MTCD algorithm and return calculated data
            logger.info(
                "Flights %s and %s have no route, "
                "running MTCD without route.",
                flight_1.flight_id,
                flight_2.flight_id,
            )
            closest_approach_point = (
                self.mtcd_toolkit.calculate_closest_approach_point(
                    self._flight_adapter_to_flight_like(flight_1),
                    self._flight_adapter_to_flight_like(flight_2),
                )
            )

            if closest_approach_point is None:
                return []
            beyond_horizon = (
                closest_approach_point.time_to_conflict_entry
                > self.ACTIVE_DETECTION_TIME_HORIZON
            )
            if beyond_horizon:
                return []

            if not self._is_conflict(
                    closest_approach_point.horizontal_distance,
                    closest_approach_point.vertical_distance,
                    closest_approach_point.time_to_closest_approach
            ):
                return []

            return [closest_approach_point]

        parsed_flightplan_1 = self.flight_plan_engine.process_flight_plan(
            flight_1.flight_id,
            flight_1.route,
        )
        parsed_flightplan_2 = self.flight_plan_engine.process_flight_plan(
            flight_2.flight_id,
            flight_2.route,
        )
        n1 = len(parsed_flightplan_1.segments)
        n2 = len(parsed_flightplan_2.segments)
        if n1 <= 1 or n2 <= 1:
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
        conflicting_segments = (
            self.boundary_checker.get_conflict_segments_within_time_boundaries(
                flight_1,
                flight_2,
                parsed_flightplan_1.segments,
                parsed_flightplan_2.segments,
                conflicting_segments,
            )
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
            closest_approach_point = (
                self.mtcd_toolkit.calculate_closest_approach_point(
                    pair_flight_1,
                    pair_flight_2,
                )
            )
            logger.info(closest_approach_point)
            time_horizon = min(time_horizon, self.ACTIVE_DETECTION_TIME_HORIZON)
            logger.info("Time horizon for precise MTCD: %f", time_horizon)

            beyond_segment = (
                closest_approach_point is None
                or closest_approach_point.time_to_conflict_entry > time_horizon
            )
            if beyond_segment:
                # Conflict isn't detected or is beyond the segment
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

    @staticmethod
    def _time_skew_seconds(
            ts_a: datetime | None,
            ts_b: datetime | None,
    ) -> float:
        """Seconds between timestamps, or 0 if either is missing.

        Args:
            ts_a: First timestamp (timezone-aware or naive).
            ts_b: Second timestamp.

        Returns:
            Non-negative seconds between the two times.
        """
        if ts_a is None or ts_b is None:
            return 0.0
        return abs((ts_a - ts_b).total_seconds())

    def _align_positions_to_common_time(
            self,
            flight_1: FlightPositionAdapter,
            flight_2: FlightPositionAdapter,
    ) -> tuple[FlightPositionAdapter, FlightPositionAdapter]:
        """Extrapolate older flight(s) to max(ts) when skew is above threshold.

        Args:
            flight_1: First flight adapter.
            flight_2: Second flight adapter.

        Returns:
            Pair of adapters sharing the reference time when alignment runs.
        """
        skew = self._time_skew_seconds(flight_1.ts, flight_2.ts)
        if skew <= self.TIME_SKEW_SYNC_THRESHOLD_SECONDS:
            return flight_1, flight_2

        if flight_1.ts is None or flight_2.ts is None:
            raise ValueError(
                "Missing timestamp on flight pair %s / %s; "
                "skipping time alignment.",
                flight_1.flight_id,
                flight_2.flight_id,
            )
            
        t_ref = max(flight_1.ts, flight_2.ts)
        f1 = flight_1
        f2 = flight_2
        if flight_1.ts < t_ref:
            f1 = self._extrapolate_to_timestamp(flight_1, t_ref)
        if flight_2.ts < t_ref:
            f2 = self._extrapolate_to_timestamp(flight_2, t_ref)
        return f1, f2

    def _extrapolate_to_timestamp(
            self,
            flight: FlightPositionAdapter,
            t_ref: datetime,
    ) -> FlightPositionAdapter:
        """Advance one flight to t_ref via route polyline or kinematic model.

        Args:
            flight: Current adapter (must have ts < t_ref).
            t_ref: Target time (same timezone semantics as flight.ts).

        Returns:
            Adapter with state at t_ref.
        """
        delta_seconds = (t_ref - flight.ts).total_seconds()
        elapsed_hours = delta_seconds / 3600.0
        if elapsed_hours <= 0:
            return flight.copy_with(ts=t_ref)

        if flight.route:
            plan = self.flight_plan_engine.process_flight_plan(
                flight.flight_id,
                flight.route,
            )
            if len(plan.segments) == 0:
                return self._extrapolate_kinematic_to_timestamp(
                    flight,
                    t_ref,
                    elapsed_hours,
                )

            idx = self.flight_plan_engine.upcoming_waypoint_in_plan(
                flight.lat,
                flight.lon,
                plan,
            )
            out = self.flight_plan_engine.extrapolate_along_route_by_time(
                flight,
                plan,
                idx,
                elapsed_hours,
            )
            return out.copy_with(ts=t_ref)

        return self._extrapolate_kinematic_to_timestamp(
            flight,
            t_ref,
            elapsed_hours,
        )

    def _extrapolate_kinematic_to_timestamp(
            self,
            flight: FlightPositionAdapter,
            t_ref: datetime,
            elapsed_hours: float,
    ) -> FlightPositionAdapter:
        """Advance position using constant ENU velocity (MTCD kinematic model).

        Args:
            flight: Current adapter.
            t_ref: Target timestamp for the returned adapter.
            elapsed_hours: Time to advance.

        Returns:
            Adapter with updated lat/lon/flight level and ts=t_ref.
        """
        fl = self._flight_adapter_to_flight_like(flight)
        pos = self.mtcd_toolkit.position_after_elapsed_hours(fl, elapsed_hours)
        fl_int = int(round(pos.flight_level))
        return flight.copy_with(
            lat=pos.lat,
            lon=pos.lon,
            flight_level=fl_int,
            ts=t_ref,
        )

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
