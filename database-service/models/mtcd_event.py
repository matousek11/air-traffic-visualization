"""MTCD event model."""

from sqlalchemy import BigInteger, Boolean, Column, Float, Index, Text, TIMESTAMP

from . import Base


class MTCDEvent(Base):
    """Model representing a Minimum Time to Conflict Detection event."""

    __tablename__ = "mtcd_event"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    flight_id_1 = Column(Text, nullable=False)
    flight_id_2 = Column(Text, nullable=False)
    detected_at = Column(TIMESTAMP(timezone=True), nullable=False)
    middle_point_lat = Column(Float, nullable=True)
    middle_point_lon = Column(Float, nullable=True)
    horizontal_distance = Column(Float, nullable=True)
    vertical_distance = Column(Float, nullable=True)
    remaining_time = Column(Float, nullable=True)
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
