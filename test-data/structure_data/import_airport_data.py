"""
Script to import airport data from airports.dat into TimescaleDB database.

This script reads airports.dat file and imports airports into the airport table.
"""

import sys
import csv
from pathlib import Path

# Add parent directories to path to import from database-service and common
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "database-service"))
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from geoalchemy2 import WKTElement

from models import Airport
from services.database import SessionLocal
from common.helpers.logging_service import LoggingService

logger = LoggingService.get_logger(__name__)


def parse_airport_line(line: str) -> tuple | None:
    """
    Parse a line from airports.dat file.
    
    Format: code,name,lat,lon,class,maxrunway,country_code,elevation
    Example: "AGAT, Uru Harbour Airport, -8.873, 161.011, Small, , BP, "
    
    Args:
        line: Line from airports.dat file
        
    Returns:
        Tuple of (code, name, lat, lon) or None if line is invalid
    """
    line = line.strip()
    if not line:
        return None
    
    # Skip header lines (lines starting with '#')
    if line.startswith('#'):
        return None
    
    try:
        # Use CSV reader to handle quoted fields and commas in names
        reader = csv.reader([line])
        parts = next(reader)
        
        if len(parts) < 4:
            return None
        
        code = parts[0].strip()
        name = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
        lat_str = parts[2].strip() if len(parts) > 2 else None
        lon_str = parts[3].strip() if len(parts) > 3 else None
        
        if not code or not lat_str or not lon_str:
            return None
        
        lat = float(lat_str)
        lon = float(lon_str)
        
        return (code, name, lat, lon)
    except (ValueError, IndexError, StopIteration) as e:
        logger.warning(f"Failed to parse line: {line[:80]}... Error: {e}")
        return None


def import_airport_data(airport_file_path: str, batch_size: int = 1000) -> None:
    """
    Import airport data from airports.dat file into database.
    
    Args:
        airport_file_path: Path to airports.dat file
        batch_size: Number of records to insert in one batch
    """
    airport_path = Path(airport_file_path)
    if not airport_path.exists():
        raise FileNotFoundError(f"Airport file not found: {airport_file_path}")
    
    db: Session = SessionLocal()
    try:
        logger.info(f"Starting import from {airport_file_path}")
        
        # Clear existing data (optional - comment out if you want to keep existing data)
        deleted_count = db.query(Airport).delete()
        logger.info(f"Deleted {deleted_count} existing airport records")
        db.commit()
        
        airports = []
        total_imported = 0
        total_skipped = 0
        
        # airports.dat files often use latin-1 encoding (ISO-8859-1)
        # Use errors='replace' to handle any problematic characters
        with open(airport_path, 'r', encoding='latin-1', errors='replace') as f:
            for line_num, line in enumerate(f, 1):
                parsed = parse_airport_line(line)
                
                if parsed is None:
                    total_skipped += 1
                    continue
                
                code, name, lat, lon = parsed
                
                # Create PostGIS POINT geometry
                geom = WKTElement(
                    f"POINT({lon} {lat})", srid=4326
                ) if lat is not None and lon is not None else None
                
                airport = Airport(
                    code=code,
                    name=name,
                    lat=lat,
                    lon=lon,
                    geom=geom,
                )
                airports.append(airport)
                
                # Insert in batches for better performance
                if len(airports) >= batch_size:
                    try:
                        db.add_all(airports)
                        db.commit()
                        total_imported += len(airports)
                        logger.info(f"Imported batch: {total_imported} airports so far...")
                    except Exception as e:
                        db.rollback()
                        logger.warning(f"Batch insert failed, trying individual inserts: {e}")
                        # Fallback to individual inserts
                        for airport_obj in airports:
                            try:
                                db.add(airport_obj)
                                db.commit()
                                total_imported += 1
                            except Exception as insert_error:
                                db.rollback()
                                logger.warning(
                                    f"Failed to insert airport {airport_obj.code}: {insert_error}"
                                )
                                total_skipped += 1
                    airports = []
        
        # Insert remaining airports
        if airports:
            try:
                db.add_all(airports)
                db.commit()
                total_imported += len(airports)
            except Exception as e:
                db.rollback()
                logger.warning(f"Final batch insert failed, trying individual inserts: {e}")
                for airport_obj in airports:
                    try:
                        db.add(airport_obj)
                        db.commit()
                        total_imported += 1
                    except Exception as insert_error:
                        db.rollback()
                        logger.warning(
                            f"Failed to insert airport {airport_obj.code}: {insert_error}"
                        )
                        total_skipped += 1
        
        logger.info(f"Import completed: {total_imported} airports imported, {total_skipped} skipped")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error importing airport data: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # Get airports.dat path (same directory as this script)
    script_dir = Path(__file__).parent
    airport_file = script_dir / "airports.dat"
    
    if not airport_file.exists():
        logger.error(f"airports.dat not found in {script_dir}")
        sys.exit(1)
    
    try:
        import_airport_data(str(airport_file))
        logger.info("Airport data import completed successfully")
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        sys.exit(1)
