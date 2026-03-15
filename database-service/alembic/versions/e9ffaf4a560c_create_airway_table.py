"""create_airway_table

Revision ID: e9ffaf4a560c
Revises: 5fc59cf9d9cc
Create Date: 2026-02-01 21:22:26.028030

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


# revision identifiers, used by Alembic.
revision: str = 'e9ffaf4a560c'
down_revision: Union[str, None] = '5fc59cf9d9cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "airway",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("start_waypoint", sa.Text, nullable=False),
        sa.Column("start_lat", sa.Float, nullable=False),
        sa.Column("start_lon", sa.Float, nullable=False),
        sa.Column("end_waypoint", sa.Text, nullable=False),
        sa.Column("end_lat", sa.Float, nullable=False),
        sa.Column("end_lon", sa.Float, nullable=False),
        sa.Column("airway_id", sa.Text, nullable=False),
        sa.Column(
            "start_geom",
            Geography(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
        sa.Column(
            "end_geom",
            Geography(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
        sa.Column(
            "route_geom",
            Geography(geometry_type="LINESTRING", srid=4326),
            nullable=True,
        ),
    )

    # Create indexes
    op.create_index("ix_airway_start_waypoint", "airway", ["start_waypoint"])
    op.create_index("ix_airway_end_waypoint", "airway", ["end_waypoint"])
    op.create_index("ix_airway_airway_id", "airway", ["airway_id"])
    
    # Create GIST indexes on geometry columns for spatial queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_airway_start_geom
        ON airway
        USING GIST (start_geom);
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_airway_end_geom
        ON airway
        USING GIST (end_geom);
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_airway_route_geom
        ON airway
        USING GIST (route_geom);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_airway_route_geom;")
    op.execute("DROP INDEX IF EXISTS idx_airway_end_geom;")
    op.execute("DROP INDEX IF EXISTS idx_airway_start_geom;")
    op.drop_index("ix_airway_airway_id", table_name="airway")
    op.drop_index("ix_airway_end_waypoint", table_name="airway")
    op.drop_index("ix_airway_start_waypoint", table_name="airway")
    op.drop_table("airway")
