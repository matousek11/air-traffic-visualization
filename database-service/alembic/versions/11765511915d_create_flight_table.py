"""create flight table

Revision ID: 11765511915d
Revises: 16f7af20650e
Create Date: 2026-01-19 21:26:17.166183

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '11765511915d'
down_revision: Union[str, None] = '16f7af20650e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flight",
        sa.Column("flight_id", sa.Text, primary_key=True),
        sa.Column("aircraft_type", sa.Text),
        sa.Column("origin", sa.Text),
        sa.Column("destination", sa.Text),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
    )

    op.create_index(
        "ix_flight_active",
        "flight",
        ["active"],
    )


def downgrade() -> None:
    op.drop_index("ix_flight_active", table_name="flight")
    op.drop_table("flight")
