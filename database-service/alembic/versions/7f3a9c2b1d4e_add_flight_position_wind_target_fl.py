"""add wind and target_flight_level to flight_position

Revision ID: 7f3a9c2b1d4e
Revises: c26e6a98ca97
Create Date: 2026-03-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "7f3a9c2b1d4e"
down_revision: Union[str, None] = "c26e6a98ca97"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "flight_position",
        sa.Column("target_flight_level", sa.Integer(), nullable=True),
    )
    op.add_column(
        "flight_position",
        sa.Column("wind_heading", sa.Float(), nullable=True),
    )
    op.add_column(
        "flight_position",
        sa.Column("wind_speed", sa.Float(), nullable=True),
    )
    op.add_column(
        "flight_position",
        sa.Column("wind_lat", sa.Float(), nullable=True),
    )
    op.add_column(
        "flight_position",
        sa.Column("wind_lon", sa.Float(), nullable=True),
    )
    op.add_column(
        "flight_position",
        sa.Column("wind_altitude", sa.Integer(), nullable=True),
    )
    op.add_column(
        "flight_position",
        sa.Column(
            "flight_plan_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("flight_position", "wind_altitude")
    op.drop_column("flight_position", "wind_lon")
    op.drop_column("flight_position", "wind_lat")
    op.drop_column("flight_position", "wind_speed")
    op.drop_column("flight_position", "wind_heading")
    op.drop_column("flight_position", "target_flight_level")
    op.drop_column("flight_position", "flight_plan_json")
