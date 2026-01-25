"""Flight model."""

from sqlalchemy import Boolean, Column, Index, Text, true

from . import Base


class Flight(Base):
    """Model representing a flight."""

    __tablename__ = "flight"

    flight_id = Column(Text, primary_key=True)
    aircraft_type = Column(Text, nullable=True)
    origin = Column(Text, nullable=True)
    destination = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, server_default=true())

    # Indexes
    __table_args__ = (
        Index("ix_flight_active", "active"),
    )

    def __repr__(self) -> str:
        return (
            f"<Flight(flight_id={self.flight_id}, "
            f"aircraft_type={self.aircraft_type}, "
            f"origin={self.origin}, "
            f"destination={self.destination}, "
            f"active={self.active})>"
        )
