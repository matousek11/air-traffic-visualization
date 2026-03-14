from typing import Dict

from common.models.flight_parser.enriched_flight_plan import EnrichedFlightPlan
from common.models.flight_parser.enriched_route_segment import EnrichedRouteSegment
from common.models.flight_position_adapter import FlightPositionAdapter
from common.helpers.flight_plan_engine import FlightPlanEngine
from common.types.bounding_cube import BoundingCube
from common.types.conflicting_segments import ConflictingSegments
from common.types.conflicting_segments_with_time import ConflictingSegmentWithTime


class BoundaryChecker:
    """Home of simple checker which determines whether routes are intersecting"""

    # conservative lat angle margin that should be enough everywhere
    HORIZONTAL_SAFE_MARGIN = 0.5
    # in flight levels
    VERTICAL_SAFE_MARGIN = 20

    def __init__(self, flight_plan_engine: FlightPlanEngine) -> None:
        self._flight_2_boundary_cache: Dict[int, BoundingCube] = {}
        self.flight_plan_engine = flight_plan_engine

    def has_intersection(
            self,
            flight_1_segments: list[EnrichedRouteSegment],
            flight_2_segments: list[EnrichedRouteSegment],
    ) -> bool:
        """
        Determines whether two flight plans have potential conflict of plans
        through bounding rectangle method.

        :param flight_1_segments: EnrichedRouteSegment flight 1 segments to be checked against other plan
        :param flight_2_segments: EnrichedRouteSegment flight 2 segments to be checked against other plan

        :return: bool True when horizontal and vertical plane is conflicting
        """
        flight_1_boundaries = self._get_boundaries_of_segments(flight_1_segments)
        flight_2_boundaries = self._get_boundaries_of_segments(flight_2_segments)

        return self._evaluate_boundaries(flight_1_boundaries, flight_2_boundaries)

    def get_conflicting_segments(
            self,
            flight_1_plan: EnrichedFlightPlan,
            flight_2_plan: EnrichedFlightPlan,
    ) -> list[ConflictingSegments]:
        """
        Find all pairs of segments between two plans that are conflicting

        :return: indexes pairs in list where each index points to conflicting segment, first segment in pair is from plan 1
        """
        detected_segment_pairs: list[ConflictingSegments] = []
        previous_segment_1 = None
        previous_segment_2 = None
        self._flight_2_boundary_cache.clear()
        for i1, segment_1 in enumerate(flight_1_plan.segments):
            if previous_segment_1 is None:
                previous_segment_1 = segment_1
                continue

            segment_1_boundary = self._get_boundaries_of_segments([previous_segment_1, segment_1])
            for i2, segment_2 in enumerate(flight_2_plan.segments):
                if previous_segment_2 is None:
                    previous_segment_2 = segment_2
                    continue

                if i2 not in self._flight_2_boundary_cache:
                    self._flight_2_boundary_cache[i2] = self._get_boundaries_of_segments(
                        [previous_segment_2, segment_2]
                    )

                if self._evaluate_boundaries(segment_1_boundary, self._flight_2_boundary_cache[i2]):
                    detected_segment_pairs.append(ConflictingSegments(i1 - 1, i1, i2 - 1, i2))

                previous_segment_2 = segment_2
            previous_segment_1 = segment_1
            previous_segment_2 = None

        return detected_segment_pairs

    def get_conflict_segments_within_time_boundaries(
            self,
            flight_1: FlightPositionAdapter,
            flight_2: FlightPositionAdapter,
            flight_1_segments: list[EnrichedRouteSegment],
            flight_2_segments: list[EnrichedRouteSegment],
            conflicting_segments: list[ConflictingSegments],
    ) -> list[ConflictingSegmentWithTime]:
        """
        Calculate time boundaries for flight entry and exit of segments in respect to possible conflict.
        When flights are not in detected segments in same time they are truncated as conflict in that segments is not possible.

        :param flight_1:
        :param flight_2:
        :param flight_1_segments: segments that were already clipped where first segment is upcoming waypoint for flight
        :param flight_2_segments: segments that were already clipped where first segment is upcoming waypoint for flight
        :param conflicting_segments: indexes of detected and possible segment conflicts

        :return: Segments pairs where conflict is still possibility even within time boundaries
        """
        if flight_1.speed == 0 or flight_2.speed == 0:
            raise ValueError("Flights must have non-zero speed")

        verified_segments: list[ConflictingSegmentWithTime] = []
        for conflicting_segment_pair in conflicting_segments:
            entry_track_miles_1 = self.flight_plan_engine.calculate_track_miles_to_waypoint(
                flight_1,
                conflicting_segment_pair.flight_1_segment_start_index,
                flight_1_segments,
            )
            remaining_time_to_entry_1 = entry_track_miles_1 / flight_1.speed
            exit_track_miles_1 = self.flight_plan_engine.calculate_track_miles_to_waypoint(
                flight_1,
                conflicting_segment_pair.flight_1_segment_end_index,
                flight_1_segments,
            )
            remaining_time_to_exit_1 = exit_track_miles_1 / flight_1.speed

            entry_track_miles_2 = self.flight_plan_engine.calculate_track_miles_to_waypoint(
                flight_2,
                conflicting_segment_pair.flight_2_segment_start_index,
                flight_2_segments,
            )
            remaining_time_to_entry_2 = entry_track_miles_2 / flight_2.speed
            exit_track_miles_2 = self.flight_plan_engine.calculate_track_miles_to_waypoint(
                flight_2,
                conflicting_segment_pair.flight_2_segment_end_index,
                flight_2_segments,
            )
            remaining_time_to_exit_2 = exit_track_miles_2 / flight_2.speed

            if self._evaluate_time_boundaries(
                remaining_time_to_entry_1,
                remaining_time_to_exit_1,
                remaining_time_to_entry_2,
                remaining_time_to_exit_2,
            ):
                verified_segment = ConflictingSegmentWithTime(
                    conflicting_segment_pair.flight_1_segment_start_index,
                    conflicting_segment_pair.flight_1_segment_end_index,
                    conflicting_segment_pair.flight_2_segment_start_index,
                    conflicting_segment_pair.flight_2_segment_end_index,
                    remaining_time_to_entry_1,
                    remaining_time_to_exit_1,
                    remaining_time_to_entry_2,
                    remaining_time_to_exit_2,
                )
                verified_segments.append(verified_segment)

        return verified_segments

    def _get_boundaries_of_segments(self, segments: list[EnrichedRouteSegment]) -> BoundingCube:
        """
        Traverse all segments and find geographical boundaries in them

        :param segments: EnrichedRouteSegment segments to be checked for boundaries
        :return: BoundingCube returns boundaries of segments with safety margin added
        """
        if len(segments) == 0:
            raise ValueError("At least one segment is required")

        first_segment = segments[0]
        min_lat = max_lat = first_segment.waypoint.lat
        min_lon = max_lon = first_segment.waypoint.lon
        min_flight_level = max_flight_level = first_segment.flight_level

        for segment in segments:
            if segment.waypoint.lat < min_lat:
                min_lat = segment.waypoint.lat

            if segment.waypoint.lat > max_lat:
                max_lat = segment.waypoint.lat

            if segment.waypoint.lon < min_lon:
                min_lon = segment.waypoint.lon

            if segment.waypoint.lon > max_lon:
                max_lon = segment.waypoint.lon

            if segment.flight_level < min_flight_level:
                min_flight_level = segment.flight_level

            if segment.flight_level > max_flight_level:
                max_flight_level = segment.flight_level

        # Margin divided by two because second boundary is going to have safe margin too
        return BoundingCube(
            min_lat - self.HORIZONTAL_SAFE_MARGIN / 2,
            max_lat + self.HORIZONTAL_SAFE_MARGIN / 2,
            min_lon - self.HORIZONTAL_SAFE_MARGIN / 2,
            max_lon + self.HORIZONTAL_SAFE_MARGIN / 2,
            min_flight_level - int(self.VERTICAL_SAFE_MARGIN / 2),
            max_flight_level + int(self.VERTICAL_SAFE_MARGIN / 2),
        )

    def _evaluate_boundaries(self, boundaries_1: BoundingCube, boundaries_2: BoundingCube) -> bool:
        """
        Evaluate whether two cube boundaries are intersecting both horizontally and vertically
        """
        has_vertical_intersection = not (
                boundaries_1.min_flight_level > boundaries_2.max_flight_level or  # Whole plan 1 is above plan 2
                boundaries_1.max_flight_level < boundaries_2.min_flight_level # Whole plan 1 is under plan 2
        )

        if not has_vertical_intersection:
            return False

        has_horizontal_intersection = not (
                boundaries_1.max_lat < boundaries_2.min_lat or  # Whole plan 1 is under plan 2
                boundaries_1.min_lat > boundaries_2.max_lat or  # Whole plan 1 is above plan 2
                boundaries_1.max_lon < boundaries_2.min_lon or  # Whole plan 1 is on the left to plan 2
                boundaries_1.min_lon > boundaries_2.max_lon  # Whole plan 1 is on the right to plan 2
        )

        return has_horizontal_intersection

    def _evaluate_time_boundaries(
            self,
            time_to_entry_1: float,
            time_to_exit_1: float,
            time_to_entry_2: float,
            time_to_exit_2: float,
    ) -> bool:
        """
        Check whether flights are in verification segments at the same time

        :param time_to_entry_1: remaining time to entry of flight 1 into segment of interest
        :param time_to_exit_1: remaining time to exit of flight 1 out of segment of interest
        :param time_to_entry_2: remaining time to entry of flight 2 into segment of interest
        :param time_to_exit_2: remaining time to exit of flight 2 out of segment of interest

        :return: true when flights in its segments in same time frame
        """
        return not (
                time_to_exit_1 < time_to_entry_2 or
                time_to_entry_1 > time_to_exit_2
        )
