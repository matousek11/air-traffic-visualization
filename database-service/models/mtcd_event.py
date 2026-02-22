"""MTCD event model."""

from sqlalchemy import BigInteger, Boolean, Column, Float, Index, Text, TIMESTAMP

from . import Base


class MTCDEvent(Base):
    """Model representing a Minimum Time to Conflict Detection event."""

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
