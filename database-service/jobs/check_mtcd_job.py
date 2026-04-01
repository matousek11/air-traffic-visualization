import time
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from common.helpers.logging_service import LoggingService
from common.helpers.mtcd_pipeline import MtcdPipeline
from common.helpers.physics_calculator import PhysicsCalculator
from common.models.flight_position_adapter import FlightPositionAdapter
from models import MTCDEvent
from repositories.flight_position_repository import FlightPositionRepository
from repositories.mtcd_event_repository import MtcdEventRepository
from services.database import SessionLocal
from common.helpers.mtcd_toolkit import Conflict

logger = LoggingService.get_logger(__name__)

class CheckMtcdJob:
    """Job that will put new mtcd events into db or update existing one for selected flights"""
    def __init__(self) -> None:
        self.mtcd_pipeline = MtcdPipeline()

    @staticmethod
    def get_job_queue() -> str:
        return 'mtcd_jobs'

    @staticmethod
    def get_job_string() -> str:
        return 'mtcd_conflict_check'

    @staticmethod
    def format_job_data(
            flight_id_1: str,
            flight_id_2: str
    ) -> dict[str, Any]:
        return {
            "type": "mtcd_conflict_check",
            "flight_id_1": flight_id_1,
            "flight_id_2": flight_id_2,
        }

    def execute(self, job_data: Dict[str, Any]) -> bool:
        start_timestamp = time.time()
        validated_input_data = self._validate_data(job_data)
        if validated_input_data is None:
            logger.error("Job validation failed, skipping execution of MTCD.")
            return False

        flight_id_1, flight_id_2 = validated_input_data
        flight_position_1 = FlightPositionRepository.get_latest_position(flight_id_1)
        flight_position_2 = FlightPositionRepository.get_latest_position(flight_id_2)
        if flight_position_1 is None or flight_position_2 is None:
            logger.error("Flight positions not found for %s or %s", flight_id_1, flight_id_2)
            logger.info("Skipping check for flights %s and %s", flight_id_1, flight_id_2)
            return True

        flight_1_position = FlightPositionAdapter(
            flight_position_1,
            flight_id_1
        )
        flight_2_position = FlightPositionAdapter(
            flight_position_2,
            flight_id_2
        )

        predicted_conflicts = self.mtcd_pipeline.run_mtcd(
            flight_1_position, flight_2_position
        )

        logger.info("Result: %s", predicted_conflicts)
        db = SessionLocal()
        if len(predicted_conflicts) == 0:
            # Set active MTCDs between selected pair of flights to inactive
            self._archive_all_conflicts(flight_id_1, flight_id_2, [], db)
            db.commit()
            db.close()
            logger.info(
                "Flights %s & %s doesn't have conflicts or they were already passed",
                flight_id_1, flight_id_2,
            )
            return True

        # get all currently existing conflicts in db
        existing_active_conflicts = MtcdEventRepository.get_all_for_pair(flight_id_1, flight_id_2)
        if existing_active_conflicts is None:
            raise ValueError("Failed to fetch data MTCD events from database")

        physics_calculator = PhysicsCalculator()
        updated_conflict_ids: list[int] = []
        for predicted_conflict in predicted_conflicts:
            existing_conflict_id = None
            for existing_conflict in existing_active_conflicts:
                #   update those that are 15 NM miles or closer to previously created conflicts
                if existing_conflict.is_close_to(physics_calculator, predicted_conflict):
                    # keep track of updated conflicts
                    updated_conflict_ids.append(existing_conflict.id)
                    existing_conflict_id = existing_conflict.id
                    break
            # Create or update predicted conflicts
            is_success = self._create_mtcd_event(
                flight_id_1, flight_id_2, predicted_conflict, db, existing_conflict_id,
            )
            if not is_success:
                db.rollback()
                db.close()
                return False

        # archive those that were created before, but now weren't detected
        is_success = self._archive_all_conflicts(
            flight_id_1, flight_id_2, updated_conflict_ids, db
        )

        # Commit all changes
        if is_success:
            db.commit()
        else:
            db.rollback()
        db.close()

        logger.info(
            "MTCD detection between %s and %s took %s seconds",
            flight_id_1, flight_id_2, time.time() - start_timestamp,
        )
        return is_success

    def _validate_data(self, job_data: Dict[str, Any]) -> tuple[str, str] | None:
        """Checks whether all required data are in job_data"""
        flight_id_1 = job_data.get("flight_id_1")
        flight_id_2 = job_data.get("flight_id_2")

        if flight_id_1 is None or flight_id_2 is None:
            logger.error("Missing flight IDs in job data")
            return None

        if flight_id_1 == flight_id_2:
            logger.warning("Same flight ID provided: %s", flight_id_1)
            return None

        return flight_id_1, flight_id_2

    def _create_mtcd_event(
            self,
            flight_id_1: str,
            flight_id_2: str,
            conflict: Conflict,
            db: Session,
            existing_conflict_id: int | None = None,
    ) -> bool:
        """Will create or update MTCD event connected to selected two flights"""
        try:
            # Check if event already exists
            query = db.query(MTCDEvent).filter(
                    MTCDEvent.flight_id_1.in_([flight_id_1, flight_id_2]),
                    MTCDEvent.flight_id_2.in_([flight_id_1, flight_id_2]),
                    MTCDEvent.active == True,
                )

            if existing_conflict_id:
                query = query.filter(MTCDEvent.id == existing_conflict_id)
            existing_event: MTCDEvent | None = query.first()

            if not existing_event:
                # Create new MTCD event
                mtcd_event = MTCDEvent.populate(flight_id_1, flight_id_2, conflict)
                db.add(mtcd_event)
                logger.info(
                    "Created MTCD event for %s and %s",
                    flight_id_1, flight_id_2,
                )
            else:
                # Update existing event
                existing_event.update_conflict(conflict)
                logger.debug(
                    "Updated MTCD event for %s and %s",
                    flight_id_1, flight_id_2,
                )
        except Exception as e:
            logger.error("Error processing MTCD conflict check: %s", e, exc_info=True)
            return False

        return True

    def _archive_all_conflicts(
            self,
            flight_id_1: str,
            flight_id_2: str,
            updated_conflict_ids: list[int],
            db: Session,
    ) -> bool:
        """Archive currently active MTCDs between selected pair of flights"""
        try:
            # Find active MTCD events between the two flights (in either order)
            active_events = (
                db.query(MTCDEvent)
                .filter(
                    MTCDEvent.id.notin_(updated_conflict_ids),
                    MTCDEvent.flight_id_1.in_([flight_id_1, flight_id_2]),
                    MTCDEvent.flight_id_2.in_([flight_id_1, flight_id_2]),
                    MTCDEvent.active == True,
                )
                .all()
            )

            if active_events:
                for event in active_events:
                    event.active = False
                    event.last_checked = datetime.now(timezone.utc)
                    logger.info(
                        "Archived MTCD event with id %s.",
                        event.id,
                    )
        except Exception as e:
            logger.error("Error archiving MTCD events: %s", e, exc_info=True)
            return False

        return True