"""add published_at to collected_data

Revision ID: a3c7e1d94f52
Revises: fb9ad3d6cb31
Create Date: 2026-03-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c7e1d94f52'
down_revision: Union[str, None] = 'fb9ad3d6cb31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('collected_data', sa.Column('published_at', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('collected_data', 'published_at')
