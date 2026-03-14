"""
Content Engine — Database Models

Tables:
1. content_engine_business_override      — per-business overrides of vertical defaults
2. content_engine_type_briefs            — 3-sentence job description per content type (Layer A)
3. content_engine_reference_library      — curated + viral reference posts (Layer B)
4. content_engine_curated_items          — human curation from trending intelligence board

Note: Vertical config (weights/enabled) is stored on the `verticals` table.
      Seasonal triggers are stored on the `vertical_seasons` table.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, JSON, Boolean, DateTime, Index, UniqueConstraint, func
)
from app.database import Base


class BusinessConfigOverride(Base):
    __tablename__ = 'content_engine_business_override'

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(Integer, nullable=False, index=True)
    config_type = Column(String(50), nullable=False)
    config_key = Column(String(100), nullable=False)
    config_value = Column(JSON, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('business_id', 'config_type', 'config_key', name='uq_business_type_key'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'business_id': self.business_id,
            'config_type': self.config_type, 'config_key': self.config_key,
            'config_value': self.config_value,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ContentTypeBrief(Base):
    """
    Layer A: Content briefs that teach the AI what makes a content type
    work for a specific vertical.
    """
    __tablename__ = 'content_engine_type_briefs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_type = Column(String(50), nullable=False)
    vertical = Column(String(50), nullable=True, index=True)
    brief_text = Column(Text, nullable=False)
    source = Column(String(20), default='manual')
    analyzed_from_count = Column(Integer, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('content_type', 'vertical', name='uq_brief_type_vertical'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'content_type': self.content_type,
            'vertical': self.vertical, 'brief_text': self.brief_text,
            'source': self.source, 'analyzed_from_count': self.analyzed_from_count,
            'active': self.active,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ReferencePost(Base):
    """
    Layer B: Curated + viral reference posts.
    These teach the AI HOW great posts sound — style, hooks, energy.
    """
    __tablename__ = 'content_engine_reference_library'

    id = Column(Integer, primary_key=True, autoincrement=True)
    vertical = Column(String(50), nullable=True, index=True)
    platform = Column(String(20), nullable=True)
    post_text = Column(Text, nullable=False)
    hook_line = Column(Text, nullable=True)
    why_it_works = Column(Text, nullable=True)
    source = Column(String(50), nullable=False)
    source_url = Column(Text, nullable=True)
    source_account = Column(String(200), nullable=True)
    engagement_views = Column(Integer, nullable=True)
    engagement_likes = Column(Integer, nullable=True)
    engagement_comments = Column(Integer, nullable=True)
    performance_tier = Column(String(20), default='good')
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_ref_vertical_platform', 'vertical', 'platform'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'vertical': self.vertical, 'platform': self.platform,
            'post_text': self.post_text, 'hook_line': self.hook_line,
            'why_it_works': self.why_it_works, 'source': self.source,
            'source_url': self.source_url, 'source_account': self.source_account,
            'engagement_views': self.engagement_views,
            'engagement_likes': self.engagement_likes,
            'engagement_comments': self.engagement_comments,
            'performance_tier': self.performance_tier,
            'active': self.active,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class CuratedItem(Base):
    """
    Human curation layer for trending intelligence items.
    """
    __tablename__ = 'content_engine_curated_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    trending_item_id = Column(String(100), nullable=True)
    item_type = Column(String(50), nullable=False)
    vertical = Column(String(50), nullable=True)
    content = Column(Text, nullable=False)
    engagement_data = Column(JSON, nullable=True)
    curation_action = Column(String(20), nullable=False)
    tagged_content_type = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    use_as_reference = Column(Boolean, default=False)
    use_as_topic = Column(Boolean, default=False)
    curated_by = Column(String(100), nullable=True)
    curated_at = Column(DateTime, server_default=func.now())
    active = Column(Boolean, default=True)

    __table_args__ = (
        Index('idx_curated_vertical_action', 'vertical', 'curation_action'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'trending_item_id': self.trending_item_id,
            'item_type': self.item_type, 'vertical': self.vertical,
            'content': self.content, 'engagement_data': self.engagement_data,
            'curation_action': self.curation_action,
            'tagged_content_type': self.tagged_content_type,
            'notes': self.notes,
            'use_as_reference': self.use_as_reference,
            'use_as_topic': self.use_as_topic,
            'curated_by': self.curated_by,
            'active': self.active,
            'curated_at': self.curated_at.isoformat() if self.curated_at else None
        }
