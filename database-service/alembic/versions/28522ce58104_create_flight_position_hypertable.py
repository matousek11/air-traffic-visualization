"""create flight_position hypertable

Revision ID: 28522ce58104
Revises: 11765511915d
Create Date: 2026-01-19 21:28:08.557883

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


# revision identifiers, used by Alembic.
revision: str = '28522ce58104'
down_revision: Union[str, None] = '11765511915d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flight_position",
        sa.Column("flight_id", sa.Text, nullable=False),
        sa.Column("ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("flight_level", sa.Integer),
        sa.Column("ground_speed_kt", sa.Integer),
        sa.Column("heading", sa.Integer),
        sa.Column("track_heading", sa.Integer),
        sa.Column("vertical_rate_fpm", sa.Integer),
        sa.Column("sector_id", sa.Text),
        sa.Column(
            "geom",
            Geography(geometry_type="POINT", srid=4326),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("flight_id", "ts"),
        sa.ForeignKeyConstraint(
            ["flight_id"],
            ["flight.flight_id"],
            ondelete="CASCADE",
        ),
    )

    # Timescale hypertable
    op.execute("""
            SELECT create_hypertable(
                'flight_position',
                'ts',
                if_not_exists => TRUE
            );
        """)

    op.execute("""
            CREATE INDEX IF NOT EXISTS idx_flight_position_geom
            ON flight_position
            USING GIST (geom);
        """)

    op.create_index(
        "ix_flight_position_ts",
        "flight_position",
        ["ts"],
    )

def downgrade() -> None:
    op.drop_index("ix_flight_position_ts", table_name="flight_position")
    op.execute("DROP INDEX IF EXISTS idx_flight_position_geom;")
    op.drop_table("flight_position")
