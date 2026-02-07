"""create_nav_table

Revision ID: c26e6a98ca97
Revises: cbe35c9f5121
Create Date: 2026-02-05 21:20:28.690262

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


# revision identifiers, used by Alembic.
revision: str = 'c26e6a98ca97'
down_revision: Union[str, None] = 'cbe35c9f5121'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nav",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("identificator", sa.Text, nullable=False),
        sa.Column('lat', sa.Float, nullable=True),
        sa.Column('lon', sa.Float, nullable=True),
        sa.Column(
            "geom",
            Geography(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
    )

    op.create_index("ix_nav_identificator", "nav", ["identificator"])
    
    # Create GIST index on geom for spatial queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_nav_geom
        ON nav
        USING GIST (geom);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_nav_geom;")
    op.drop_index("ix_nav_identificator", table_name="nav")
    op.drop_table("nav")
