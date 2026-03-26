"""DB schema for denormalized flight position hypertable."""

from sqlalchemy import text
from sqlalchemy.engine import Connection


def drop_and_create_hypertable(conn: Connection, table_name: str) -> None:
    """Drop the table if it exists, then create it as a Timescale hypertable.

    Args:
        conn: Open SQLAlchemy connection (within a transaction).
        table_name: Name of the table to create.
    """
    conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
    create_sql = f"""
        CREATE TABLE {table_name} (
            sample_time TIMESTAMPTZ NOT NULL,
            time_over TIMESTAMPTZ NOT NULL,
            flight_id TEXT NOT NULL,
            aircraft_type TEXT,
            origin TEXT,
            destination TEXT,
            lat DOUBLE PRECISION,
            lon DOUBLE PRECISION,
            flight_level INTEGER,
            route_string TEXT,
            ground_speed_kt INTEGER,
            track_heading INTEGER,
            vertical_rate_fpm INTEGER,
            heading INTEGER,
            PRIMARY KEY (flight_id, sample_time)
        )
    """
    conn.execute(text(create_sql))
    ht_sql = (
        f"SELECT create_hypertable('{table_name}', 'sample_time', "
        f"if_not_exists => TRUE)"
    )
    conn.execute(text(ht_sql))
    conn.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS ix_{table_name}_flight_id "
            f"ON {table_name} (flight_id)",
        ),
    )
