"""add is_all_time_favourite to collected_data

Revision ID: b7f2e4a91c03
Revises: a3c7e1d94f52
Create Date: 2026-03-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7f2e4a91c03"
down_revision: Union[str, None] = "a3c7e1d94f52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "collected_data",
        sa.Column("is_all_time_favourite", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_collected_data_all_time_favourite", "collected_data", ["is_all_time_favourite"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_collected_data_all_time_favourite", table_name="collected_data")
    op.drop_column("collected_data", "is_all_time_favourite")
