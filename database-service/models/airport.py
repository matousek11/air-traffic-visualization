"""Airport model."""

from geoalchemy2 import Geography
from sqlalchemy import Column, Float, Text

from . import Base


class Airport(Base):
    """Model representing an airport."""

    __tablename__ = "airport"

    code = Column(Text, primary_key=True)
    name = Column(Text, nullable=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    geom = Column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
    )

    # Note: GIST index on geom is created via raw SQL in migration
    # and cannot be defined here using standard SQLAlchemy

    def __repr__(self) -> str:
        return (
            f"<Airport(code={self.code}, "
            f"name={self.name}, lat={self.lat}, lon={self.lon})>"
        )
