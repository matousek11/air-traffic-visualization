"""
FastAPI application for database service.
Exposes endpoints for querying MTCD events and other database data.
"""

from typing import List

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from models import Flight, FlightPosition, MTCDEvent
from models.flight_detail_api import FlightDetailResponse
from models.mtcd_event_response import MTCDEventResponse
from services.database import SessionLocal
from services.flight_snapshot_service import FlightSnapshotService

app = FastAPI(
    title="Database Service API",
    description="API for querying MTCD events and flight data",
    version="1.0.0",
)

_flight_snapshot_service = FlightSnapshotService()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/mtcd-events", response_model=List[MTCDEventResponse])
def get_mtcd_events(
    active_only: bool = Query(
        True,
        description=(
            "If True, return only active events, if False, return all."
        ),
    ),
) -> List[MTCDEventResponse] | None:
    """
    Get MTCD events from the database.

    Returns:
        By default, returns only active events, set active_only=false to return all.
    """
    db: Session = SessionLocal()
    try:
        query = db.query(MTCDEvent).order_by(MTCDEvent.detected_at.desc())
        if active_only:
            query = query.filter(MTCDEvent.active.is_(True))
        events = query.all()

        return [
            MTCDEventResponse.model_validate(event)
            for event in events
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching MTCD events: {str(e)}",
        ) from e
    finally:
        db.close()


@app.get(
    "/flights",
    response_model=(
        List[FlightDetailResponse] | FlightDetailResponse
    ),
)
def get_flights(
    flight_id: str | None = Query(
        None,
        description=(
            "If set, return one flight, otherwise list all active flights."
        ),
    ),
) -> List[FlightDetailResponse] | FlightDetailResponse:
    """
    List flights with the latest positions.

    Returns:
        List of flight details, or one detail when flight_id is provided.

    Raises:
        HTTPException: 404 if flight_id is set but not found, 500 on errors.
    """
    db: Session = SessionLocal()
    try:
        if flight_id is None:
            return _flight_snapshot_service.list_flight_details(db)
        detail = _flight_snapshot_service.get_flight_detail(db, flight_id)
        if detail is None:
            raise HTTPException(
                status_code=404,
                detail="Flight not found",
            )
        return detail
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching flights: {str(e)}",
        ) from e
    finally:
        db.close()


@app.delete("/reset-for-new-simulation", status_code=status.HTTP_204_NO_CONTENT)
def reset_db_for_new_simulation():
    """
    Reset database for new simulation - deletes all MTCD events, flights, and flight positions.
    """
    db: Session = SessionLocal()
    try:
        db.query(MTCDEvent).delete()
        db.query(Flight).delete()
        db.query(FlightPosition).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"Error resetting database: {str(e)}"
        )
    finally:
        db.close()


@app.get("/waypoints/{name}")
def get_waypoint(
    name: str,
    lat: float = Query(..., description="Latitude of aircraft position"),
    lon: float = Query(..., description="Longitude of aircraft position"),
) -> dict:
    """
    Get waypoint coordinates by name, searching in both fix and nav tables.
    
    Args:
        name: Waypoint identifier/name
        lat: Latitude of aircraft position
        lon: Longitude of aircraft position
    
    Returns:
        Dictionary with name, lat, and lon
    
    Raises:
        HTTPException 404: If waypoint not found
    """
    query = text("""
        WITH combined AS (
            SELECT identificator AS name, lat, lon, geom, 0 AS source_ord
            FROM fix WHERE identificator = :name
            UNION ALL
            SELECT identificator, lat, lon, geom, 1
            FROM nav WHERE identificator = :name
        )
        SELECT name, lat, lon
        FROM combined
        ORDER BY
            (geom IS NOT NULL) DESC,
            ST_Distance(
                COALESCE(geom, ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography),
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            ) ASC NULLS LAST,
            source_ord ASC
        LIMIT 1;
    """)
    db: Session = SessionLocal()
    try:
        result = db.execute(query, {"name": name, "lat": lat, "lon": lon})
        row = result.fetchone()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Waypoint '{name}' not found in fix or nav tables"
            )
        return {"name": row.name, "lat": row.lat, "lon": row.lon}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching waypoint: {str(e)}",
        ) from e
    finally:
        db.close()


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
