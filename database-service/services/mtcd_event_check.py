"""MTCD event check process - finds flights within 30 minutes for possible closest approach."""

from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from common.helpers.logging_service import LoggingService
from services.database import SessionLocal

logger = LoggingService.get_logger(__name__)


class MTCDEventCheck:
    """MTCD event check process - finds flights within 30 minutes for possible closest approach."""

    def __init__(self, time_threshold_hours: float = 0.5):
        """
        Initialize MTCD event check.

        Args:
            time_threshold_hours: Time threshold in hours (default: 0.5 = 30 minutes)
        """
        self.time_threshold_hours = time_threshold_hours

    def find_potential_conflicts(
        self, db: Optional[Session] = None
    ) -> Dict[str, List[str]]:
        """
        Find all flights that are within time_threshold of closest approach.

        Returns:
            Dictionary mapping flight_id to list of flight_ids that are
            within time threshold of closest approach
        """
        if db is None:
            db = SessionLocal()
        try:
            return self._find_potential_conflicts(db)
        finally:
            db.close()


    def _find_potential_conflicts(self, db: Session) -> Dict[str, List[str]]:
        """
        Internal method to find potential conflicts using PostGIS for distance calculations.

        Uses TimescaleDB/PostGIS to efficiently calculate distances and filter conflicts.
        """
        # SQL query that:
        # 1. Gets latest position for each active flight
        # 2. Calculates distance between all pairs using PostGIS
        # 3. Calculates time to meeting (distance / (speed1 + speed2))
        # 4. Filters by time threshold
        query = text("""
            WITH latest_positions AS (
                SELECT DISTINCT ON (fp1.flight_id)
                    fp1.flight_id,
                    fp1.lat,
                    fp1.lon,
                    fp1.ground_speed_kt,
                    fp1.geom
                FROM flight_position fp1
                INNER JOIN flight f ON f.flight_id = fp1.flight_id
                WHERE f.active = true
                    AND fp1.lat IS NOT NULL
                    AND fp1.lon IS NOT NULL
                    AND fp1.ground_speed_kt IS NOT NULL
                    AND fp1.ground_speed_kt > 0
                ORDER BY fp1.flight_id, fp1.ts DESC
            )
            SELECT
                lp1.flight_id AS flight_id_1,
                lp2.flight_id AS flight_id_2,
                -- Calculate distance in nautical miles using PostGIS
                -- ST_Distance returns meters for geography type, convert to NM
                (ST_Distance(lp1.geom, lp2.geom) / 1852.0) AS distance_nm,
                -- Calculate time to meeting in hours
                -- distance_nm / (speed1 + speed2) in knots
                CASE
                    WHEN (lp1.ground_speed_kt + lp2.ground_speed_kt) > 0 THEN
                        (ST_Distance(lp1.geom, lp2.geom) / 1852.0) / 
                        (lp1.ground_speed_kt + lp2.ground_speed_kt)
                    ELSE NULL
                END AS time_to_meeting_hours
            FROM latest_positions lp1
            CROSS JOIN latest_positions lp2
            WHERE lp1.flight_id < lp2.flight_id  -- Avoid duplicates and self-pairs
                AND (ST_Distance(lp1.geom, lp2.geom) / 1852.0) / 
                    (lp1.ground_speed_kt + lp2.ground_speed_kt) <= :time_threshold
                AND (ST_Distance(lp1.geom, lp2.geom) / 1852.0) / 
                    (lp1.ground_speed_kt + lp2.ground_speed_kt) >= 0
        """)

        result = db.execute(query, {"time_threshold": self.time_threshold_hours})

        # Build conflicts dictionary
        # Query already filters with flight_id_1 < flight_id_2,
        conflicts: Dict[str, List[str]] = {}
        conflict_count = 0

        for row in result:
            flight_id_1 = row.flight_id_1
            flight_id_2 = row.flight_id_2

            if flight_id_1 not in conflicts:
                conflicts[flight_id_1] = []
            conflicts[flight_id_1].append(flight_id_2)

            conflict_count += 1

        logger.info("Found %s potential conflict pairs", conflict_count)
        return conflicts
