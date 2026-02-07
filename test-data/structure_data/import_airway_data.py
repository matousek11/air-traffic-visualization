"""
Script to import airway data from awy.dat into TimescaleDB database.

This script reads awy.dat file and imports airway segments into the airway table.
"""

import sys
from pathlib import Path

# Add parent directories to path to import from database-service and common
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "database-service"))
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from geoalchemy2 import WKTElement

from models import Airway
from services.database import SessionLocal
from common.helpers.logging_service import LoggingService

logger = LoggingService.get_logger(__name__)


def parse_airway_line(line: str) -> tuple | None:
    """
    Parse a line from awy.dat file.
    
    Format: start_waypoint start_lat start_lon end_waypoint end_lat end_lon direction base_alt top_alt airway_id
    Example: "00MKK  22.528056 -156.170961 BITTA  23.528031 -155.478836 1 012 460 R464"
    
    Args:
        line: Line from awy.dat file
        
    Returns:
        Tuple of (start_waypoint, start_lat, start_lon, end_waypoint, end_lat, end_lon,
                 direction, base_altitude, top_altitude, airway_id) or None if line is invalid
    """
    line = line.strip()
    if not line:
        return None
    
    try:
        parts = line.split()
        # Minimum 10 parts: start_wp, start_lat, start_lon, end_wp, end_lat, end_lon, dir, base_alt, top_alt, airway_id
        # But airway_id can contain spaces or dashes, so we need at least 10 parts
        if len(parts) < 10:
            logger.warning(f"Not enough parts in line: {line}")
            return None
        
        # First 9 parts are fixed format
        start_waypoint = parts[0].strip()
        start_lat = float(parts[1])
        start_lon = float(parts[2])
        end_waypoint = parts[3].strip()
        end_lat = float(parts[4])
        end_lon = float(parts[5])
        direction = int(parts[6])
        base_altitude = int(parts[7])  # in hundreds of feet
        top_altitude = int(parts[8])  # in hundreds of feet
        # airway_id is everything after part 8, joined back together (can contain dashes, spaces)
        airway_id = ' '.join(parts[9:]).strip()
        
        return (
            start_waypoint, start_lat, start_lon,
            end_waypoint, end_lat, end_lon,
            direction, base_altitude, top_altitude, airway_id
        )
    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse line: {line[:80]}... Error: {e}")
        return None


def import_airway_data(airway_file_path: str, batch_size: int = 1000) -> None:
    """
    Import airway data from awy.dat file into database.
    
    Args:
        airway_file_path: Path to awy.dat file
        batch_size: Number of records to insert in one batch
    """
    airway_path = Path(airway_file_path)
    if not airway_path.exists():
        raise FileNotFoundError(f"Airway file not found: {airway_file_path}")
    
    db: Session = SessionLocal()
    try:
        logger.info(f"Starting import from {airway_file_path}")
        
        # Clear existing data (optional - comment out if you want to keep existing data)
        deleted_count = db.query(Airway).delete()
        logger.info(f"Deleted {deleted_count} existing airway records")
        db.commit()
        
        airways = []
        total_imported = 0
        total_skipped = 0
        
        with open(airway_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                parsed = parse_airway_line(line)
                
                if parsed is None:
                    total_skipped += 1
                    continue
                
                (
                    start_waypoint, start_lat, start_lon,
                    end_waypoint, end_lat, end_lon,
                    direction, base_altitude, top_altitude, airway_id
                ) = parsed
                
                # Create PostGIS geometries
                start_geom = WKTElement(
                    f"POINT({start_lon} {start_lat})", srid=4326
                ) if start_lat is not None and start_lon is not None else None
                
                end_geom = WKTElement(
                    f"POINT({end_lon} {end_lat})", srid=4326
                ) if end_lat is not None and end_lon is not None else None
                
                # Create LINESTRING for the route segment
                route_geom = WKTElement(
                    f"LINESTRING({start_lon} {start_lat}, {end_lon} {end_lat})", srid=4326
                ) if (start_lat is not None and start_lon is not None and 
                      end_lat is not None and end_lon is not None) else None
                
                airway = Airway(
                    start_waypoint=start_waypoint,
                    start_lat=start_lat,
                    start_lon=start_lon,
                    end_waypoint=end_waypoint,
                    end_lat=end_lat,
                    end_lon=end_lon,
                    direction=direction,
                    base_altitude=base_altitude,
                    top_altitude=top_altitude,
                    airway_id=airway_id,
                    start_geom=start_geom,
                    end_geom=end_geom,
                    route_geom=route_geom,
                )
                airways.append(airway)
                
                # Insert in batches for better performance
                if len(airways) >= batch_size:
                    try:
                        db.add_all(airways)
                        db.commit()
                        total_imported += len(airways)
                        logger.info(f"Imported batch: {total_imported} airways so far...")
                    except Exception as e:
                        db.rollback()
                        logger.warning(f"Batch insert failed, trying individual inserts: {e}")
                        # Fallback to individual inserts
                        for airway_obj in airways:
                            try:
                                db.add(airway_obj)
                                db.commit()
                                total_imported += 1
                            except Exception as insert_error:
                                db.rollback()
                                logger.warning(
                                    f"Failed to insert airway {airway_obj.airway_id} "
                                    f"({airway_obj.start_waypoint} -> {airway_obj.end_waypoint}): {insert_error}"
                                )
                                total_skipped += 1
                    airways = []
        
        # Insert remaining airways
        if airways:
            try:
                db.add_all(airways)
                db.commit()
                total_imported += len(airways)
            except Exception as e:
                db.rollback()
                logger.warning(f"Final batch insert failed, trying individual inserts: {e}")
                for airway_obj in airways:
                    try:
                        db.add(airway_obj)
                        db.commit()
                        total_imported += 1
                    except Exception as insert_error:
                        db.rollback()
                        logger.warning(
                            f"Failed to insert airway {airway_obj.airway_id} "
                            f"({airway_obj.start_waypoint} -> {airway_obj.end_waypoint}): {insert_error}"
                        )
                        total_skipped += 1
        
        logger.info(f"Import completed: {total_imported} airways imported, {total_skipped} skipped")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error importing airway data: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # Get awy.dat path (same directory as this script)
    script_dir = Path(__file__).parent
    airway_file = script_dir / "awy.dat"
    
    if not airway_file.exists():
        logger.error(f"awy.dat not found in {script_dir}")
        sys.exit(1)
    
    try:
        import_airway_data(str(airway_file))
        logger.info("Airway data import completed successfully")
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        sys.exit(1)
