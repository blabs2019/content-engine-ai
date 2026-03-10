"""add reach_score to collected_data

Revision ID: c4d8f2a71e05
Revises: b7f2e4a91c03
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c4d8f2a71e05"
down_revision: Union[str, None] = "b7f2e4a91c03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "collected_data",
        sa.Column("reach_score", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("collected_data", "reach_score")
