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
        sa.Column("flight_id_1", sa.Text, nullable=False),
        sa.Column("flight_id_2", sa.Text, nullable=False),
        sa.Column("detected_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('middle_point_lat', sa.Float, nullable=True),
        sa.Column('middle_point_lon', sa.Float, nullable=True),
        sa.Column("horizontal_distance", sa.Float),
        sa.Column("vertical_distance", sa.Float),
        sa.Column("remaining_time", sa.Float),
        sa.Column("active", sa.Boolean, default=True),
        sa.Column("last_checked", sa.TIMESTAMP(timezone=True)),
    )

    op.create_index("ix_mtcd_event_active", "mtcd_event", ["active"])
    op.create_index("ix_mtcd_event_detected_at", "mtcd_event", ["detected_at"])


def downgrade() -> None:
    op.drop_index("ix_mtcd_event_active", table_name="mtcd_event")
    op.drop_index("ix_mtcd_event_detected_at", table_name="mtcd_event")
    op.drop_table("mtcd_event")
