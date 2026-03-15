"""
Script to import nav data from nav.dat into TimescaleDB database.

This script reads nav.dat file and imports navigation aid points into the nav table.
Format: type lat lon ... identificator name
Example: "2  38.08777778 -077.32491667      0   396  50    0.0 APH  A P HILL NDB"
"""

import sys
from pathlib import Path

# Add parent directories to path to import from database-service and common
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "database-service"))
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from geoalchemy2 import WKTElement

from models import Nav
from services.database import SessionLocal
from common.helpers.logging_service import LoggingService

logger = LoggingService.get_logger(__name__)


def parse_nav_line(line: str) -> tuple[float, float, str] | None:
    """
    Parse a line from nav.dat file.
    
    Format: type lat lon elevation frequency range ... identificator name
    Example: "2  38.08777778 -077.32491667      0   396  50    0.0 APH  A P HILL NDB"
    
    Args:
        line: Line from nav.dat file
        
    Returns:
        Tuple of (lat, lon, identificator) or None if line is invalid
    """
    line = line.strip()
    if not line:
        return None
    
    # Skip header lines (first 3 lines are usually header)
    if line.startswith("810") or "Version" in line or "Copyright" in line:
        return None
    
    try:
        # Split by whitespace
        parts = line.split()
        
        if len(parts) < 8:
            return None
        
        # First part is type (usually "2"), skip it
        # Second part is lat
        # Third part is lon
        try:
            lat = float(parts[1])
            lon = float(parts[2])
        except (ValueError, IndexError):
            return None
        
        # Identificator is usually at position 7 (index 7) after:
        # type, lat, lon, elevation, frequency, range, another_number
        # But we'll search for it more flexibly
        identificator = None
        
        # Try position 7 first (most common case)
        if len(parts) > 7:
            candidate = parts[7].strip()
            # Identificator is usually 1-4 characters, alphanumeric, may contain numbers
            if 1 <= len(candidate) <= 4 and candidate.replace('.', '').replace('-', '').isalnum():
                identificator = candidate
            else:
                # Search from position 3 onwards for a short alphanumeric string
                for i in range(3, min(10, len(parts))):  # Check first 10 parts
                    candidate = parts[i].strip()
                    # Identificator is usually 1-4 characters, alphanumeric
                    if (1 <= len(candidate) <= 4 and 
                        candidate.replace('.', '').replace('-', '').isalnum() and
                        not candidate.replace('.', '').replace('-', '').replace('+', '').isdigit()):
                        # Make sure it's not a float
                        try:
                            float(candidate)
                            continue  # Skip if it's a number
                        except ValueError:
                            identificator = candidate
                            break
        
        if identificator is None:
            return None
        
        return (lat, lon, identificator)
    except (ValueError, IndexError) as e:
        logger.warning("Failed to parse line: %s... Error: %s", line[:50], e)
        return None


def import_nav_data(nav_file_path: str, batch_size: int = 1000) -> None:
    """
    Import nav data from nav.dat file into database.
    
    Args:
        nav_file_path: Path to nav.dat file
        batch_size: Number of records to insert in one batch
    """
    nav_path = Path(nav_file_path)
    if not nav_path.exists():
        raise FileNotFoundError(f"Nav file not found: {nav_file_path}")
    
    db: Session = SessionLocal()
    try:
        logger.info("Starting import from %s", nav_file_path)
        
        # Clear existing data (optional - comment out if you want to keep existing data)
        deleted_count = db.query(Nav).delete()
        logger.info("Deleted %s existing nav records", deleted_count)
        db.commit()
        
        navs = []
        total_imported = 0
        total_skipped = 0
        
        with open(nav_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                parsed = parse_nav_line(line)
                
                if parsed is None:
                    total_skipped += 1
                    if line_num <= 10:  # Log first few skipped lines for debugging
                        logger.debug("Skipped line %s: %s...", line_num, line[:50])
                    continue
                
                lat, lon, identificator = parsed
                
                # Create PostGIS POINT geometry
                geom = WKTElement(f"POINT({lon} {lat})", srid=4326) if lat is not None and lon is not None else None
                
                nav = Nav(
                    identificator=identificator,
                    lat=lat,
                    lon=lon,
                    geom=geom
                )
                navs.append(nav)
                
                # Insert in batches for better performance
                if len(navs) >= batch_size:
                    try:
                        db.add_all(navs)
                        db.commit()
                        total_imported += len(navs)
                        logger.info("Imported batch: %s navs so far...", total_imported)
                    except Exception as e:
                        db.rollback()
                        logger.warning("Batch insert failed, trying individual inserts: %s", e)
                        # Fallback to individual inserts
                        for nav_obj in navs:
                            try:
                                db.add(nav_obj)
                                db.commit()
                                total_imported += 1
                            except Exception as insert_error:
                                db.rollback()
                                logger.warning(
                                    "Failed to insert nav %s: %s",
                                    nav_obj.identificator, insert_error,
                                )
                                total_skipped += 1
                    navs = []
        
        # Insert remaining navs
        if navs:
            try:
                db.add_all(navs)
                db.commit()
                total_imported += len(navs)
            except Exception as e:
                db.rollback()
                logger.warning("Final batch insert failed, trying individual inserts: %s", e)
                for nav_obj in navs:
                    try:
                        db.add(nav_obj)
                        db.commit()
                        total_imported += 1
                    except Exception as insert_error:
                        db.rollback()
                        logger.warning(
                            "Failed to insert nav %s: %s",
                            nav_obj.identificator, insert_error,
                        )
                        total_skipped += 1
        
        logger.info(
            "Import completed: %s navs imported, %s skipped",
            total_imported, total_skipped,
        )
        
    except Exception as e:
        db.rollback()
        logger.error("Error importing nav data: %s", e, exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # Get nav.dat path (same directory as this script)
    script_dir = Path(__file__).parent
    nav_file = script_dir / "nav.dat"
    
    if not nav_file.exists():
        logger.error("nav.dat not found in %s", script_dir)
        sys.exit(1)
    
    try:
        import_nav_data(str(nav_file))
        logger.info("Nav data import completed successfully")
    except Exception as e:
        logger.error("Import failed: %s", e, exc_info=True)
        sys.exit(1)
