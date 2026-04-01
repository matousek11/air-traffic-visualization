"""Repository for latest flight positions joined with flight metadata."""

from typing import List, Tuple

from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from models import Flight, FlightPosition


def _has_complete_kinematics() -> ColumnElement[bool]:
    """Check whether row has complete kinematics data.

    Returns:
        SQLAlchemy boolean expression for NOT NULL checks.
    """
    return and_(
        FlightPosition.heading.isnot(None),
        FlightPosition.ground_speed_kt.isnot(None),
        FlightPosition.track_heading.isnot(None),
        FlightPosition.vertical_rate_fpm.isnot(None),
        FlightPosition.flight_level.isnot(None),
    )


class FlightSnapshotRepository:
    """Loads the latest snapshot per flight for API responses."""

    @staticmethod
    def list_latest_positions_with_flights(
        db: Session,
    ) -> List[Tuple[FlightPosition, Flight]]:
        """
        Return the newest flight_position row per active flight with Flight row.

        Args:
            db: SQLAlchemy session.

        Returns:
            List of (FlightPosition, Flight) pairs ordered by flight_id.
        """
        subq = (
            db.query(
                FlightPosition.flight_id.label("fid"),
                func.max(FlightPosition.ts).label("max_ts"),
            )
            .join(Flight, Flight.flight_id == FlightPosition.flight_id)
            .filter(Flight.active.is_(True))
            .filter(_has_complete_kinematics())
            .group_by(FlightPosition.flight_id)
            .subquery()
        )

        rows = (
            db.query(FlightPosition, Flight)
            .join(
                subq,
                (FlightPosition.flight_id == subq.c.fid)
                & (FlightPosition.ts == subq.c.max_ts),
            )
            .join(Flight, Flight.flight_id == FlightPosition.flight_id)
            .filter(Flight.active.is_(True))
            .order_by(FlightPosition.flight_id)
            .all()
        )
        return rows

    @staticmethod
    def get_latest_position_with_flight(
        db: Session,
        flight_id: str,
    ) -> Tuple[FlightPosition, Flight] | None:
        """
        Return the newest position for one active flight, or None if missing.

        Args:
            db: SQLAlchemy session.
            flight_id: Flight identifier.

        Returns:
            (FlightPosition, Flight) or None if not found or inactive.
        """
        flight = (
            db.query(Flight)
            .filter(
                Flight.flight_id == flight_id,
                Flight.active.is_(True),
            )
            .first()
        )
        if flight is None:
            return None

        position = (
            db.query(FlightPosition)
            .filter(FlightPosition.flight_id == flight_id)
            .filter(_has_complete_kinematics())
            .order_by(FlightPosition.ts.desc())
            .first()
        )
        if position is None:
            return None

        return (position, flight)
