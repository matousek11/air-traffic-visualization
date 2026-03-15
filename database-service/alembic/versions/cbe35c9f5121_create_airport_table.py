"""create_airport_table

Revision ID: cbe35c9f5121
Revises: e9ffaf4a560c
Create Date: 2026-02-01 21:41:29.155399

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


# revision identifiers, used by Alembic.
revision: str = 'cbe35c9f5121'
down_revision: Union[str, None] = 'e9ffaf4a560c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "airport",
        sa.Column("code", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column(
            "geom",
            Geography(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
        sa.Column("uuid", sa.Text, nullable=False),
    )
    
    # Create GIST index on geometry column for spatial queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_airport_geom
        ON airport
        USING GIST (geom);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_airport_geom;")
    op.drop_table("airport")
