"""MTCD event model."""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, Float, Index, Text, TIMESTAMP

from common.helpers.mtcd_toolkit import Conflict
from common.helpers.physics_calculator import PhysicsCalculator
from . import Base


class MTCDEvent(Base):
    """Model representing a Minimum Time to Conflict Detection event."""

    SAME_CONFLICT_DISTANCE_IN_NM = 15

    __tablename__ = "mtcd_event"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    flight_id_1 = Column(Text)
    flight_id_2 = Column(Text)
    detected_at = Column(TIMESTAMP(timezone=True))
    middle_point_lat = Column(Float)
    middle_point_lon = Column(Float)
    horizontal_distance = Column(Float)
    vertical_distance = Column(Float)
    remaining_time = Column(Float)
    flight_1_conflict_entry_lat = Column(Float)
    flight_1_conflict_entry_lon = Column(Float)
    flight_1_conflict_entry_flight_level = Column(Float)
    flight_1_conflict_exit_lat = Column(Float)
    flight_1_conflict_exit_lon = Column(Float)
    flight_1_conflict_exit_flight_level = Column(Float)
    flight_2_conflict_entry_lat = Column(Float)
    flight_2_conflict_entry_lon = Column(Float)
    flight_2_conflict_entry_flight_level = Column(Float)
    flight_2_conflict_exit_lat = Column(Float)
    flight_2_conflict_exit_lon = Column(Float)
    flight_2_conflict_exit_flight_level = Column(Float)
    active = Column(Boolean, default=True, nullable=False)
    last_checked = Column(TIMESTAMP(timezone=True), nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_mtcd_event_active", "active"),
        Index("ix_mtcd_event_detected_at", "detected_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<MTCDEvent(id={self.id}, "
            f"flight_id_1={self.flight_id_1}, "
            f"flight_id_2={self.flight_id_2}, "
            f"detected_at={self.detected_at}, "
            f"active={self.active})>"
        )

    def is_close_to(
            self,
            physics_calculator: PhysicsCalculator,
            conflict: Conflict
    ) -> bool:
        """Checks whether location is close to conflict"""
        distance = physics_calculator.get_distance_between_positions(
            self.middle_point_lat,
            self.middle_point_lon,
            conflict.middle_point.lat,
            conflict.middle_point.lon,
        )

        return physics_calculator.km_to_nm(distance) < self.SAME_CONFLICT_DISTANCE_IN_NM

    def update_conflict(self, conflict: Conflict) -> None:
        """Update existing MTCD event with newly calculated conflict"""
        self.horizontal_distance = conflict.horizontal_distance
        self.vertical_distance = conflict.vertical_distance
        self.remaining_time = conflict.time_to_conflict_entry
        self.middle_point_lat = conflict.middle_point.lat
        self.middle_point_lon = conflict.middle_point.lon
        self.flight_1_conflict_entry_lat = conflict.flight_1_conflict_entry_pos.lat
        self.flight_1_conflict_entry_lon = conflict.flight_1_conflict_entry_pos.lon
        self.flight_1_conflict_entry_flight_level = conflict.flight_1_conflict_entry_pos.flight_level
        self.flight_1_conflict_exit_lat = conflict.flight_1_conflict_exit_pos.lat
        self.flight_1_conflict_exit_lon = conflict.flight_1_conflict_exit_pos.lon
        self.flight_1_conflict_exit_flight_level = conflict.flight_1_conflict_exit_pos.flight_level
        self.flight_2_conflict_entry_lat = conflict.flight_2_conflict_entry_pos.lat
        self.flight_2_conflict_entry_lon = conflict.flight_2_conflict_entry_pos.lon
        self.flight_2_conflict_entry_flight_level = conflict.flight_2_conflict_entry_pos.flight_level
        self.flight_2_conflict_exit_lat = conflict.flight_2_conflict_exit_pos.lat
        self.flight_2_conflict_exit_lon = conflict.flight_2_conflict_exit_pos.lon
        self.flight_2_conflict_exit_flight_level = conflict.flight_2_conflict_exit_pos.flight_level
        self.last_checked = datetime.now(timezone.utc)

    @staticmethod
    def populate(
            flight_id_1: str,
            flight_id_2: str,
            conflict: Conflict
    ) -> "MTCDEvent":
        """Populate new MTCD event object from conflict for the pair of flights"""
        return MTCDEvent(
            flight_id_1=flight_id_1,
            flight_id_2=flight_id_2,
            detected_at=datetime.now(timezone.utc),
            horizontal_distance=conflict.horizontal_distance,
            vertical_distance=conflict.vertical_distance,
            remaining_time=conflict.time_to_conflict_entry,
            middle_point_lat=conflict.middle_point.lat,
            middle_point_lon=conflict.middle_point.lon,
            flight_1_conflict_entry_lat=conflict.flight_1_conflict_entry_pos.lat,
            flight_1_conflict_entry_lon=conflict.flight_1_conflict_entry_pos.lon,
            flight_1_conflict_entry_flight_level=conflict.flight_1_conflict_entry_pos.flight_level,
            flight_1_conflict_exit_lat=conflict.flight_1_conflict_exit_pos.lat,
            flight_1_conflict_exit_lon=conflict.flight_1_conflict_exit_pos.lon,
            flight_1_conflict_exit_flight_level=conflict.flight_1_conflict_exit_pos.flight_level,
            flight_2_conflict_entry_lat=conflict.flight_2_conflict_entry_pos.lat,
            flight_2_conflict_entry_lon=conflict.flight_2_conflict_entry_pos.lon,
            flight_2_conflict_entry_flight_level=conflict.flight_2_conflict_entry_pos.flight_level,
            flight_2_conflict_exit_lat=conflict.flight_2_conflict_exit_pos.lat,
            flight_2_conflict_exit_lon=conflict.flight_2_conflict_exit_pos.lon,
            flight_2_conflict_exit_flight_level=conflict.flight_2_conflict_exit_pos.flight_level,
            active=True,
            last_checked=datetime.now(timezone.utc),
        )
