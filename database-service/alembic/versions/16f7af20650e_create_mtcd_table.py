"""create mtcd table

Revision ID: 16f7af20650e
Revises: 
Create Date: 2026-01-19 21:12:02.225768

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '16f7af20650e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mtcd_event",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("flight_id_1", sa.Text),
        sa.Column("flight_id_2", sa.Text),
        sa.Column("detected_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("middle_point_lat", sa.Float),
        sa.Column("middle_point_lon", sa.Float),
        sa.Column("horizontal_distance", sa.Float),
        sa.Column("vertical_distance", sa.Float),
        sa.Column("remaining_time", sa.Float),
        sa.Column("flight_1_conflict_entry_lat", sa.Float),
        sa.Column("flight_1_conflict_entry_lon", sa.Float),
        sa.Column("flight_1_conflict_entry_flight_level", sa.Float),
        sa.Column("flight_1_conflict_exit_lat", sa.Float),
        sa.Column("flight_1_conflict_exit_lon", sa.Float),
        sa.Column("flight_1_conflict_exit_flight_level", sa.Float),
        sa.Column("flight_2_conflict_entry_lat", sa.Float),
        sa.Column("flight_2_conflict_entry_lon", sa.Float),
        sa.Column("flight_2_conflict_entry_flight_level", sa.Float),
        sa.Column("flight_2_conflict_exit_lat", sa.Float),
        sa.Column("flight_2_conflict_exit_lon", sa.Float),
        sa.Column("flight_2_conflict_exit_flight_level", sa.Float),
        sa.Column("active", sa.Boolean, default=True, nullable=False),
        sa.Column("last_checked", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_index("ix_mtcd_event_active", "mtcd_event", ["active"])
    op.create_index("ix_mtcd_event_detected_at", "mtcd_event", ["detected_at"])


def downgrade() -> None:
    op.drop_index("ix_mtcd_event_active", table_name="mtcd_event")
    op.drop_index("ix_mtcd_event_detected_at", table_name="mtcd_event")
    op.drop_table("mtcd_event")
