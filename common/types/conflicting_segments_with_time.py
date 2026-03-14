from typing import NamedTuple


class ConflictingSegmentWithTime(NamedTuple):
    """DTO with extended attributes containing remaining time to entry/exit of segment"""
    flight_1_segment_start_index: int
    flight_1_segment_end_index: int
    flight_2_segment_start_index: int
    flight_2_segment_end_index: int
    flight_1_segment_entry_time: float
    flight_1_segment_exit_time: float
    flight_2_segment_entry_time: float
    flight_2_segment_exit_time: float

    def __repr__(self) -> str:
        """Return string with all attributes for debugging when object is printed."""
        parts = [f"{name}={getattr(self, name)!r}" for name in self._fields]
        return f"ConflictingSegmentWithTime({', '.join(parts)})"