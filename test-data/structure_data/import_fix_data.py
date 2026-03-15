"""
Script to import fix data from fix.dat into TimescaleDB database.

This script reads fix.dat file and imports navigation fix points into the fix table.
"""

import sys
from pathlib import Path

# Add parent directories to path to import from database-service and common
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "database-service"))
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from geoalchemy2 import WKTElement

from models import Fix
from services.database import SessionLocal
from common.helpers.logging_service import LoggingService

logger = LoggingService.get_logger(__name__)


def parse_fix_line(line: str) -> tuple[float, float, str] | None:
    """
    Parse a line from fix.dat file.
    
    Format: lat lon identificator
    Example: "00.000000  000.000000 0000E"
    
    Args:
        line: Line from fix.dat file
        
    Returns:
        Tuple of (lat, lon, identificator) or None if line is invalid
    """
    line = line.strip()
    if not line:
        return None
    
    try:
        parts = line.split()
        if len(parts) != 3:
            return None
        
        lat = float(parts[0])
        lon = float(parts[1])
        identificator = parts[2].strip()
        
        return (lat, lon, identificator)
    except (ValueError, IndexError) as e:
        logger.warning("Failed to parse line: %s... Error: %s", line[:50], e)
        return None


def import_fix_data(fix_file_path: str, batch_size: int = 1000) -> None:
    """
    Import fix data from fix.dat file into database.
    
    Args:
        fix_file_path: Path to fix.dat file
        batch_size: Number of records to insert in one batch
    """
    fix_path = Path(fix_file_path)
    if not fix_path.exists():
        raise FileNotFoundError(f"Fix file not found: {fix_file_path}")
    
    db: Session = SessionLocal()
    try:
        logger.info("Starting import from %s", fix_file_path)
        
        # Clear existing data (optional - comment out if you want to keep existing data)
        deleted_count = db.query(Fix).delete()
        logger.info("Deleted %s existing fix records", deleted_count)
        db.commit()
        
        fixes = []
        total_imported = 0
        total_skipped = 0
        
        with open(fix_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                parsed = parse_fix_line(line)
                
                if parsed is None:
                    total_skipped += 1
                    continue
                
                lat, lon, identificator = parsed
                
                # Create PostGIS POINT geometry
                geom = WKTElement(f"POINT({lon} {lat})", srid=4326) if lat is not None and lon is not None else None
                
                fix = Fix(
                    identificator=identificator,
                    lat=lat,
                    lon=lon,
                    geom=geom
                )
                fixes.append(fix)
                
                # Insert in batches for better performance
                if len(fixes) >= batch_size:
                    try:
                        db.add_all(fixes)
                        db.commit()
                        total_imported += len(fixes)
                        logger.info("Imported batch: %s fixes so far...", total_imported)
                    except Exception as e:
                        db.rollback()
                        logger.warning("Batch insert failed, trying individual inserts: %s", e)
                        # Fallback to individual inserts
                        for fix_obj in fixes:
                            try:
                                db.add(fix_obj)
                                db.commit()
                                total_imported += 1
                            except Exception as insert_error:
                                db.rollback()
                                logger.warning(
                                    "Failed to insert fix %s: %s",
                                    fix_obj.identificator, insert_error,
                                )
                                total_skipped += 1
                    fixes = []
        
        # Insert remaining fixes
        if fixes:
            try:
                db.add_all(fixes)
                db.commit()
                total_imported += len(fixes)
            except Exception as e:
                db.rollback()
                logger.warning("Final batch insert failed, trying individual inserts: %s", e)
                for fix_obj in fixes:
                    try:
                        db.add(fix_obj)
                        db.commit()
                        total_imported += 1
                    except Exception as insert_error:
                        db.rollback()
                        logger.warning(
                            "Failed to insert fix %s: %s",
                            fix_obj.identificator, insert_error,
                        )
                        total_skipped += 1
        
        logger.info(
            "Import completed: %s fixes imported, %s skipped",
            total_imported, total_skipped,
        )
        
    except Exception as e:
        db.rollback()
        logger.error("Error importing fix data: %s", e, exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # Get fix.dat path (same directory as this script)
    script_dir = Path(__file__).parent
    fix_file = script_dir / "fix.dat"
    
    if not fix_file.exists():
        logger.error("fix.dat not found in %s", script_dir)
        sys.exit(1)
    
    try:
        import_fix_data(str(fix_file))
        logger.info("Fix data import completed successfully")
    except Exception as e:
        logger.error("Import failed: %s", e, exc_info=True)
        sys.exit(1)
