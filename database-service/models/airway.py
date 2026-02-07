"""Airway model."""

from geoalchemy2 import Geography
from sqlalchemy import Column, Float, Index, Integer, Text

from . import Base


class Airway(Base):
    """Model representing an airway segment."""

    __tablename__ = "airway"

    id = Column(Integer, primary_key=True, autoincrement=True)
    start_waypoint = Column(Text, nullable=False)
    start_lat = Column(Float, nullable=False)
    start_lon = Column(Float, nullable=False)
    end_waypoint = Column(Text, nullable=False)
    end_lat = Column(Float, nullable=False)
    end_lon = Column(Float, nullable=False)
    direction = Column(Integer, nullable=False)  # 1 = bidirectional, 0 = one-way
    base_altitude = Column(Integer, nullable=False)  # in hundreds of feet
    top_altitude = Column(Integer, nullable=False)  # in hundreds of feet
    airway_id = Column(Text, nullable=False)
    start_geom = Column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
    )
    end_geom = Column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
    )
    route_geom = Column(
        Geography(geometry_type="LINESTRING", srid=4326),
        nullable=True,
    )

    # Indexes
    __table_args__ = (
        Index("ix_airway_start_waypoint", "start_waypoint"),
        Index("ix_airway_end_waypoint", "end_waypoint"),
        Index("ix_airway_airway_id", "airway_id"),
        # Note: GIST indexes on geom columns are created via raw SQL in migration
        # and cannot be defined here using standard SQLAlchemy
    )

    def get_next_point(self, current_point: str) -> str:
        if self.start_waypoint != current_point:
            return self.start_waypoint

        return self.end_waypoint

    def __repr__(self) -> str:
        return (
            f"<Airway(id={self.id}, airway_id={self.airway_id}, "
            f"start={self.start_waypoint}, end={self.end_waypoint}, "
            f"base_alt={self.base_altitude * 100}ft, "
            f"top_alt={self.top_altitude * 100}ft)>"
        )
