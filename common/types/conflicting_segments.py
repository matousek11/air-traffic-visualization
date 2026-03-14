from typing import NamedTuple


class ConflictingSegments(NamedTuple):
    """Used as DTO for segments detected for conflict"""
    flight_1_segment_start_index: int
    flight_1_segment_end_index: int
    flight_2_segment_start_index: int
    flight_2_segment_end_index: int