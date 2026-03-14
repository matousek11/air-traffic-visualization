"""Flight Position model."""

from geoalchemy2 import Geography
from sqlalchemy import Column, Float, ForeignKey, Index, Integer, Text, TIMESTAMP

from . import Base


class FlightPosition(Base):
    """Model representing a flight position at a specific time."""

    __tablename__ = "flight_position"

    flight_id = Column(
        Text,
        ForeignKey("flight.flight_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    ts = Column(TIMESTAMP(timezone=True), primary_key=True, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    flight_level = Column(Integer, nullable=True)
    ground_speed_kt = Column(Integer, nullable=True)
    heading = Column(Integer, nullable=True)
    track_heading = Column(Integer, nullable=True)
    vertical_rate_fpm = Column(Integer, nullable=True)
    sector_id = Column(Text, nullable=True)
    route = Column(Text, nullable=True)
    geom = Column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=False,
    )

    # Indexes
    __table_args__ = (
        Index("ix_flight_position_ts", "ts"),
        # Note: GIST index on geom is created via raw SQL in migration
        # and cannot be defined here using standard SQLAlchemy
    )

    def __repr__(self) -> str:
        return (
            f"<FlightPosition(flight_id={self.flight_id}, "
            f"ts={self.ts}, "
            f"lat={self.lat}, "
            f"lon={self.lon}, "
            f"flight_level={self.flight_level})>"
        )
