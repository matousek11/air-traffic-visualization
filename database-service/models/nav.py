"""Nav model."""

from geoalchemy2 import Geography
from sqlalchemy import Column, Float, Index, Integer, Text

from . import Base


class Nav(Base):
    """Model representing a navigation aid point."""

    __tablename__ = "nav"

    id = Column(Integer, primary_key=True, autoincrement=True)
    identificator = Column(Text, nullable=False)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    geom = Column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
    )
    uuid = Column(Text, nullable=False)

    # Indexes
    __table_args__ = (
        Index("ix_nav_identificator", "identificator"),
        # Note: GIST index on geom is created via raw SQL in migration
        # and cannot be defined here using standard SQLAlchemy
    )

    def __repr__(self) -> str:
        return (
            f"<Nav(id={self.id}, identificator={self.identificator}, "
            f"lat={self.lat}, lon={self.lon}, uuid={self.uuid})>"
        )
