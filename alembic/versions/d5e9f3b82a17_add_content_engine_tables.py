"""add content_engine tables

Revision ID: d5e9f3b82a17
Revises: c4d8f2a71e05
Create Date: 2026-03-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd5e9f3b82a17'
down_revision: Union[str, None] = 'c4d8f2a71e05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add content engine columns to existing verticals table
    op.add_column('verticals', sa.Column('content_type_weights', sa.JSON(), nullable=True))
    op.add_column('verticals', sa.Column('content_types_enabled', sa.JSON(), nullable=True))

    # Add content engine columns to existing vertical_seasons table
    op.add_column('vertical_seasons', sa.Column('trigger_system', sa.String(100), nullable=True))
    op.add_column('vertical_seasons', sa.Column('month_start', sa.Integer(), nullable=True))
    op.add_column('vertical_seasons', sa.Column('month_end', sa.Integer(), nullable=True))
    op.add_column('vertical_seasons', sa.Column('priority', sa.Integer(), server_default='5'))
    op.add_column('vertical_seasons', sa.Column('active', sa.Boolean(), server_default='1'))

    # content_engine_business_override
    op.create_table(
        'content_engine_business_override',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('business_id', sa.Integer(), nullable=False),
        sa.Column('config_type', sa.String(50), nullable=False),
        sa.Column('config_key', sa.String(100), nullable=False),
        sa.Column('config_value', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('business_id', 'config_type', 'config_key', name='uq_business_type_key'),
    )
    op.create_index('ix_content_engine_business_override_business_id', 'content_engine_business_override', ['business_id'])

    # content_engine_type_briefs
    op.create_table(
        'content_engine_type_briefs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('content_type', sa.String(50), nullable=False),
        sa.Column('vertical', sa.String(50), nullable=True),
        sa.Column('brief_text', sa.Text(), nullable=False),
        sa.Column('source', sa.String(20), default='manual'),
        sa.Column('analyzed_from_count', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('content_type', 'vertical', name='uq_brief_type_vertical'),
    )
    op.create_index('ix_content_engine_type_briefs_vertical', 'content_engine_type_briefs', ['vertical'])

    # content_engine_reference_library
    op.create_table(
        'content_engine_reference_library',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('vertical', sa.String(50), nullable=True),
        sa.Column('platform', sa.String(20), nullable=True),
        sa.Column('post_text', sa.Text(), nullable=False),
        sa.Column('hook_line', sa.Text(), nullable=True),
        sa.Column('why_it_works', sa.Text(), nullable=True),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('source_account', sa.String(200), nullable=True),
        sa.Column('engagement_views', sa.Integer(), nullable=True),
        sa.Column('engagement_likes', sa.Integer(), nullable=True),
        sa.Column('engagement_comments', sa.Integer(), nullable=True),
        sa.Column('performance_tier', sa.String(20), default='good'),
        sa.Column('active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_content_engine_reference_library_vertical', 'content_engine_reference_library', ['vertical'])
    op.create_index('idx_ref_vertical_platform', 'content_engine_reference_library', ['vertical', 'platform'])

    # content_engine_curated_items
    op.create_table(
        'content_engine_curated_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('trending_item_id', sa.String(100), nullable=True),
        sa.Column('item_type', sa.String(50), nullable=False),
        sa.Column('vertical', sa.String(50), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('engagement_data', sa.JSON(), nullable=True),
        sa.Column('curation_action', sa.String(20), nullable=False),
        sa.Column('tagged_content_type', sa.String(50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('use_as_reference', sa.Boolean(), default=False),
        sa.Column('use_as_topic', sa.Boolean(), default=False),
        sa.Column('curated_by', sa.String(100), nullable=True),
        sa.Column('curated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_curated_vertical_action', 'content_engine_curated_items', ['vertical', 'curation_action'])


def downgrade() -> None:
    op.drop_table('content_engine_curated_items')
    op.drop_table('content_engine_reference_library')
    op.drop_table('content_engine_type_briefs')
    op.drop_table('content_engine_business_override')

    op.drop_column('vertical_seasons', 'active')
    op.drop_column('vertical_seasons', 'priority')
    op.drop_column('vertical_seasons', 'month_end')
    op.drop_column('vertical_seasons', 'month_start')
    op.drop_column('vertical_seasons', 'trigger_system')

    op.drop_column('verticals', 'content_types_enabled')
    op.drop_column('verticals', 'content_type_weights')
