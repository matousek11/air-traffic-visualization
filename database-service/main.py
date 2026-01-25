"""
FastAPI application for database service.
Exposes endpoints for querying MTCD events and other database data.
"""

from typing import List

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from models import Flight, FlightPosition, MTCDEvent
from models.mtcd_event_response import MTCDEventResponse
from services.database import SessionLocal

app = FastAPI(
    title="Database Service API",
    description="API for querying MTCD events and flight data",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/mtcd-events", response_model=List[MTCDEventResponse])
def get_active_mtcd_events() -> List[MTCDEventResponse]:
    """
    Get all currently active MTCD events from the database.

    Returns:
        List of active MTCD events
    """
    db: Session = SessionLocal()
    try:
        events = (
            db.query(MTCDEvent)
            .filter(MTCDEvent.active == True)  # noqa: E712
            .order_by(MTCDEvent.detected_at.desc())
            .all()
        )

        return [MTCDEventResponse.model_validate(event) for event in events]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching MTCD events: {str(e)}")
    finally:
        db.close()

@app.get("/reset-for-new-simulation", status_code=status.HTTP_204_NO_CONTENT)
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


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
