"""create fix table

Revision ID: 5fc59cf9d9cc
Revises: 28522ce58104
Create Date: 2026-02-01 16:55:49.999037

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


# revision identifiers, used by Alembic.
revision: str = '5fc59cf9d9cc'
down_revision: Union[str, None] = '28522ce58104'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fix",
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

    op.create_index("ix_fix_identificator", "fix", ["identificator"])
    
    # Create GIST index on geom for spatial queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_fix_geom
        ON fix
        USING GIST (geom);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_fix_geom;")
    op.drop_index("ix_fix_identificator", table_name="fix")
    op.drop_table("fix")
